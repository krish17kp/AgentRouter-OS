//! Axum runtime for the versioned local HTTP API.
//!
//! The Python service remains the release authority until the complete HTTP
//! contract, middleware and client compatibility suites pass in every platform
//! job. This router is safe by default: model execution is never performed.

use std::{
    collections::HashMap,
    net::SocketAddr,
    path::PathBuf,
    sync::{
        atomic::{AtomicU64, Ordering},
        Arc,
    },
    time::{SystemTime, UNIX_EPOCH},
};

use agentrouter_limits::{
    client_key, CachedResponse, IdempotencyCache, RateLimiter, RATE_EXEMPT_PATHS,
};
use axum::{
    body::{to_bytes, Body, Bytes},
    extract::{ConnectInfo, Path, Request, State},
    http::{header, HeaderValue, StatusCode},
    middleware::{self, Next},
    response::{Html, IntoResponse, Redirect, Response},
    routing::{get, post},
    Json, Router,
};
use serde::de::DeserializeOwned;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use tokio::sync::Mutex;
use tower_http::{catch_panic::CatchPanicLayer, cors::CorsLayer};
use unicode_general_category::{get_general_category, GeneralCategory};

use crate::{
    schemas::{
        first_validation_message, ClassifyRequest, DryRunRequest, FeedbackRequest, RequestKind,
        RouteRequest,
    },
    service::{self, ServiceError},
};

const API_KEY_ENV: &str = "AGENTROUTER_API_KEY";
const CORS_ORIGINS_ENV: &str = "AGENTROUTER_CORS_ORIGINS";
const REQUEST_ID_HEADER: &str = "x-request-id";
const MAX_MIDDLEWARE_ENTRIES: usize = 10_000;
const MAX_CACHED_BODY_BYTES: usize = 1_048_576;

#[derive(Clone)]
struct ApiState {
    home: PathBuf,
    request_counter: Arc<AtomicU64>,
    rate_limiter: Arc<RateLimiter>,
    idempotency_cache: Arc<IdempotencyCache>,
    flights: Arc<Mutex<HashMap<String, Arc<Mutex<()>>>>>,
}

#[derive(Debug)]
struct ApiError {
    status: StatusCode,
    code: &'static str,
    message: String,
}

impl ApiError {
    fn unauthorized() -> Self {
        Self {
            status: StatusCode::UNAUTHORIZED,
            code: "unauthorized",
            message: "invalid or missing API key".to_string(),
        }
    }

    fn not_found(message: impl Into<String>) -> Self {
        Self {
            status: StatusCode::NOT_FOUND,
            code: "not_found",
            message: message.into(),
        }
    }

    fn validation(message: impl Into<String>) -> Self {
        Self {
            status: StatusCode::UNPROCESSABLE_ENTITY,
            code: "validation_error",
            message: message.into(),
        }
    }

    fn registry_unavailable() -> Self {
        Self {
            status: StatusCode::SERVICE_UNAVAILABLE,
            code: "registry_unavailable",
            message:
                "registry unavailable or invalid; run 'agentrouter doctor' locally for details"
                    .to_string(),
        }
    }

    fn internal() -> Self {
        Self {
            status: StatusCode::INTERNAL_SERVER_ERROR,
            code: "internal_error",
            message: "internal server error".to_string(),
        }
    }

    fn rate_limited() -> Self {
        Self {
            status: StatusCode::TOO_MANY_REQUESTS,
            code: "rate_limited",
            message: "too many requests; slow down".to_string(),
        }
    }

    fn unavailable() -> Self {
        Self {
            status: StatusCode::SERVICE_UNAVAILABLE,
            code: "unavailable",
            message: "server capacity reached; retry later".to_string(),
        }
    }

    fn payload_too_large() -> Self {
        Self {
            status: StatusCode::PAYLOAD_TOO_LARGE,
            code: "request_too_large",
            message: "request body is too large".to_string(),
        }
    }
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        (
            self.status,
            Json(json!({
                "error": {"code": self.code, "message": self.message}
            })),
        )
            .into_response()
    }
}

impl From<ServiceError> for ApiError {
    fn from(error: ServiceError) -> Self {
        match error {
            ServiceError::Validation(message) => Self::validation(message),
            ServiceError::Registry(_) => Self::registry_unavailable(),
            ServiceError::Internal(_) => Self::internal(),
        }
    }
}

/// Build the API router. The home directory is explicit so embedded callers
/// and tests never have to mutate process-global state after startup.
pub fn router(home: PathBuf) -> Router {
    let state = ApiState {
        home,
        request_counter: Arc::new(AtomicU64::new(0)),
        rate_limiter: Arc::new(RateLimiter::new(None, None)),
        idempotency_cache: Arc::new(IdempotencyCache::new(None)),
        flights: Arc::new(Mutex::new(HashMap::new())),
    };
    let app = Router::new()
        .route("/", get(|| async { Redirect::temporary("/docs") }))
        .route("/docs", get(docs))
        .route("/openapi.json", get(openapi))
        .route("/health", get(health))
        .route("/ready", get(ready))
        .route("/v1/models", get(models))
        .route("/v1/hosts", get(hosts))
        .route("/v1/classify", post(classify))
        .route("/v1/route", post(route_task))
        .route("/v1/decisions/{decision_id}", get(decision))
        .route("/v1/feedback", post(feedback))
        .route("/v1/execute/dry-run", post(dry_run))
        .fallback(not_found)
        .with_state(state.clone())
        .layer(CatchPanicLayer::custom(|_panic| {
            ApiError::internal().into_response()
        }))
        .layer(middleware::from_fn_with_state(state.clone(), api_key_auth));

    let origins = cors_origins();
    if !origins.is_empty() {
        let cors = CorsLayer::new()
            .allow_origin(origins)
            .allow_methods([axum::http::Method::GET, axum::http::Method::POST])
            .allow_headers([
                header::CONTENT_TYPE,
                header::HeaderName::from_static("idempotency-key"),
                header::HeaderName::from_static(REQUEST_ID_HEADER),
            ])
            .expose_headers([header::HeaderName::from_static(REQUEST_ID_HEADER)]);
        let app = app.layer(cors).layer(middleware::from_fn_with_state(
            state.clone(),
            limits_and_idempotency,
        ));
        return app.layer(middleware::from_fn_with_state(state, request_id));
    }
    app.layer(middleware::from_fn_with_state(
        state.clone(),
        limits_and_idempotency,
    ))
    .layer(middleware::from_fn_with_state(state, request_id))
}

/// Run the HTTP service until it receives a graceful shutdown signal.
pub fn run(bind: String, home: PathBuf) -> Result<(), Box<dyn std::error::Error>> {
    std::panic::set_hook(Box::new(|_| {
        eprintln!("api.panic: request handler panicked; details withheld from logs");
    }));
    let runtime = tokio::runtime::Builder::new_multi_thread()
        .enable_all()
        .build()?;
    runtime.block_on(async move {
        let listener = tokio::net::TcpListener::bind(&bind).await?;
        let address = listener.local_addr()?;
        println!("LISTENING {address}");
        let app = router(home).into_make_service_with_connect_info::<SocketAddr>();
        axum::serve(listener, app)
            .with_graceful_shutdown(async {
                let _ = tokio::signal::ctrl_c().await;
            })
            .await?;
        Ok::<(), Box<dyn std::error::Error>>(())
    })
}

fn cors_origins() -> Vec<HeaderValue> {
    std::env::var(CORS_ORIGINS_ENV)
        .unwrap_or_default()
        .split(',')
        .filter_map(|value| {
            let origin = value.trim().trim_end_matches('/');
            if origin.is_empty() || origin == "*" {
                return None;
            }
            HeaderValue::from_str(origin).ok()
        })
        .collect()
}

async fn request_id(State(state): State<ApiState>, request: Request, next: Next) -> Response {
    let supplied = request
        .headers()
        .get(REQUEST_ID_HEADER)
        .and_then(|value| value.to_str().ok())
        .map(str::to_owned);
    let id = supplied.unwrap_or_else(|| {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos();
        let sequence = state.request_counter.fetch_add(1, Ordering::Relaxed);
        format!("{nanos:x}-{sequence:x}")
    });
    let header_value = HeaderValue::try_from(id.as_str())
        .unwrap_or_else(|_| HeaderValue::from_static("request-id-invalid"));
    let mut response = next.run(request).await;
    if response.status() == StatusCode::SERVICE_UNAVAILABLE {
        eprintln!("api.registry_error request_id={id}");
    } else if response.status().is_server_error() {
        eprintln!("api.internal_error request_id={id}");
    }
    response
        .headers_mut()
        .insert(REQUEST_ID_HEADER, header_value);
    response
}

async fn api_key_auth(State(_state): State<ApiState>, request: Request, next: Next) -> Response {
    if request.uri().path().starts_with("/v1/") {
        let expected = std::env::var(API_KEY_ENV).unwrap_or_default();
        if !expected.is_empty() {
            let provided = request
                .headers()
                .get("x-api-key")
                .and_then(|value| value.to_str().ok());
            if !provided.is_some_and(|key| constant_time_eq(key.as_bytes(), expected.as_bytes())) {
                return ApiError::unauthorized().into_response();
            }
        }
    }
    next.run(request).await
}

async fn limits_and_idempotency(
    State(state): State<ApiState>,
    mut request: Request,
    next: Next,
) -> Response {
    let path = request.uri().path().to_string();
    let expected = std::env::var(API_KEY_ENV).unwrap_or_default();
    let provided = request
        .headers()
        .get("x-api-key")
        .and_then(|value| value.to_str().ok())
        .map(str::to_owned);
    let authenticated = expected.is_empty()
        || provided
            .as_deref()
            .is_some_and(|key| constant_time_eq(key.as_bytes(), expected.as_bytes()));

    if !RATE_EXEMPT_PATHS.contains(&path.as_str()) {
        let trusted_key = if !expected.is_empty() && authenticated {
            provided.as_deref()
        } else {
            None
        };
        let client_ip = request
            .extensions()
            .get::<ConnectInfo<SocketAddr>>()
            .map(|ConnectInfo(address)| address.ip().to_string())
            .unwrap_or_else(|| "unknown".to_string());
        let trusted_hash = trusted_key.map(|key| format!("{:x}", Sha256::digest(key.as_bytes())));
        let rate_key = client_key(trusted_hash.as_deref(), Some(&client_ip));
        let (allowed, retry_after) = state.rate_limiter.check(&rate_key);
        if !allowed {
            let mut response = ApiError::rate_limited().into_response();
            if let Ok(value) = HeaderValue::try_from(retry_after.to_string()) {
                response.headers_mut().insert("retry-after", value);
            }
            return response;
        }
    }

    let idempotency_key = request
        .headers()
        .get("idempotency-key")
        .and_then(|value| value.to_str().ok())
        .filter(|value| !value.is_empty())
        .map(str::to_owned);
    if request.method() != axum::http::Method::POST || !authenticated {
        return next.run(request).await;
    }
    let Some(idempotency_key) = idempotency_key else {
        return next.run(request).await;
    };

    let body = std::mem::replace(request.body_mut(), Body::empty());
    let body = match to_bytes(body, MAX_CACHED_BODY_BYTES).await {
        Ok(body) => body,
        Err(_) => return ApiError::payload_too_large().into_response(),
    };
    *request.body_mut() = Body::from(body.clone());

    let identity = if expected.is_empty() {
        "local"
    } else {
        provided.as_deref().unwrap_or_default()
    };
    let cache_key = idempotency_cache_key(identity, &idempotency_key, &path, &body);
    let Some(flight) = acquire_flight(&state, &cache_key).await else {
        return ApiError::unavailable().into_response();
    };
    let flight_guard = flight.clone().lock_owned().await;

    if let Some(cached) = state.idempotency_cache.get(&cache_key) {
        drop(flight_guard);
        let mut response = Response::new(Body::from(cached.body));
        *response.status_mut() =
            StatusCode::from_u16(cached.status).unwrap_or(StatusCode::INTERNAL_SERVER_ERROR);
        if let Some(content_type) = cached
            .media_type
            .and_then(|value| HeaderValue::try_from(value).ok())
        {
            response
                .headers_mut()
                .insert(header::CONTENT_TYPE, content_type);
        }
        response
            .headers_mut()
            .insert("idempotency-replay", HeaderValue::from_static("true"));
        release_flight(&state, &cache_key, &flight).await;
        return response;
    }

    let response = next.run(request).await;
    let (parts, response_body) = response.into_parts();
    let response_body = match to_bytes(response_body, usize::MAX).await {
        Ok(body) => body,
        Err(_) => {
            drop(flight_guard);
            release_flight(&state, &cache_key, &flight).await;
            return ApiError::internal().into_response();
        }
    };
    let mut response = Response::from_parts(parts, Body::from(response_body.clone()));
    if response.status().is_success() && response_body.len() <= MAX_CACHED_BODY_BYTES {
        state.idempotency_cache.put(
            &cache_key,
            CachedResponse {
                status: response.status().as_u16(),
                body: response_body.to_vec(),
                media_type: response
                    .headers()
                    .get(header::CONTENT_TYPE)
                    .and_then(|value| value.to_str().ok())
                    .map(str::to_owned),
            },
        );
    }
    response
        .headers_mut()
        .insert("idempotency-replay", HeaderValue::from_static("false"));
    drop(flight_guard);
    release_flight(&state, &cache_key, &flight).await;
    response
}

fn idempotency_cache_key(identity: &str, key: &str, path: &str, body: &[u8]) -> String {
    let mut digest = Sha256::new();
    digest.update(identity.as_bytes());
    digest.update([0]);
    digest.update(key.as_bytes());
    digest.update([0]);
    digest.update(path.as_bytes());
    digest.update([0]);
    digest.update(body);
    format!("{:x}", digest.finalize())
}

async fn acquire_flight(state: &ApiState, key: &str) -> Option<Arc<Mutex<()>>> {
    let mut flights = state.flights.lock().await;
    if let Some(flight) = flights.get(key) {
        return Some(flight.clone());
    }
    if flights.len() >= MAX_MIDDLEWARE_ENTRIES {
        flights.retain(|_, flight| Arc::strong_count(flight) > 1 || flight.try_lock().is_err());
        if flights.len() >= MAX_MIDDLEWARE_ENTRIES {
            return None;
        }
    }
    let flight = Arc::new(Mutex::new(()));
    flights.insert(key.to_string(), flight.clone());
    Some(flight)
}

async fn release_flight(state: &ApiState, key: &str, flight: &Arc<Mutex<()>>) {
    let mut flights = state.flights.lock().await;
    let can_remove = flights.get(key).is_some_and(|current| {
        Arc::ptr_eq(current, flight)
            && Arc::strong_count(current) == 2
            && current.try_lock().is_ok()
    });
    if can_remove {
        flights.remove(key);
    }
}

fn constant_time_eq(left: &[u8], right: &[u8]) -> bool {
    let mut diff = left.len() ^ right.len();
    for index in 0..left.len().max(right.len()) {
        diff |= usize::from(*left.get(index).unwrap_or(&0) ^ *right.get(index).unwrap_or(&0));
    }
    diff == 0
}

fn safe_echo(value: &str) -> String {
    let cleaned: String = value
        .chars()
        .filter(|character| {
            !matches!(
                get_general_category(*character),
                GeneralCategory::Control | GeneralCategory::Format
            ) && !matches!(*character, '\u{2028}' | '\u{2029}')
        })
        .take(65)
        .collect();
    if cleaned.chars().count() > 64 {
        format!("{}…", cleaned.chars().take(64).collect::<String>())
    } else {
        cleaned
    }
}

fn decode<T: DeserializeOwned>(body: Bytes, kind: RequestKind) -> Result<T, ApiError> {
    let value: Value = serde_json::from_slice(&body).map_err(|error| {
        let byte_offset = body
            .split(|byte| *byte == b'\n')
            .take(error.line().saturating_sub(1))
            .map(|line| line.len().saturating_add(1))
            .sum::<usize>()
            .saturating_add(error.column().saturating_sub(1));
        ApiError::validation(format!("{byte_offset}: JSON decode error"))
    })?;
    if let Some(message) = first_validation_message(&value, kind) {
        return Err(ApiError::validation(message));
    }
    serde_json::from_value(value).map_err(|_| ApiError::validation("request body is invalid"))
}

fn service_result<T>(result: Result<T, ServiceError>) -> Result<T, ApiError> {
    result.map_err(ApiError::from)
}

async fn blocking<T, F>(work: F) -> Result<T, ApiError>
where
    T: Send + 'static,
    F: FnOnce() -> Result<T, ServiceError> + Send + 'static,
{
    let result = tokio::task::spawn_blocking(work)
        .await
        .map_err(|_| ApiError::internal())?;
    service_result(result)
}

async fn health() -> Json<Value> {
    Json(json!({"status": "ok"}))
}

async fn ready(State(state): State<ApiState>) -> Result<Json<Value>, ApiError> {
    let home = state.home;
    blocking(move || service::list_models(&home).map(|_| ())).await?;
    Ok(Json(json!({"status": "ready"})))
}

async fn models(State(state): State<ApiState>) -> Result<Json<Value>, ApiError> {
    let home = state.home;
    let rows = blocking(move || service::list_models(&home)).await?;
    Ok(Json(Value::Array(rows)))
}

async fn hosts() -> Json<Value> {
    Json(Value::Array(service::list_hosts()))
}

async fn classify(State(_state): State<ApiState>, body: Bytes) -> Result<Json<Value>, ApiError> {
    let request: ClassifyRequest = decode(body, RequestKind::Classify)?;
    let result = blocking(move || service::classify_task(&request)).await?;
    Ok(Json(result))
}

async fn route_task(State(state): State<ApiState>, body: Bytes) -> Result<Json<Value>, ApiError> {
    let request: RouteRequest = decode(body, RequestKind::Route)?;
    let home = state.home;
    let result = blocking(move || service::route_task(&home, &request)).await?;
    Ok(Json(result))
}

async fn decision(
    State(state): State<ApiState>,
    Path(decision_id): Path<String>,
) -> Result<Json<Value>, ApiError> {
    let home = state.home;
    let safe_id = safe_echo(&decision_id);
    let result = blocking(move || service::get_decision(&home, &decision_id)).await?;
    match result {
        Some(payload) => Ok(Json(payload)),
        None => Err(ApiError::not_found(format!("no decision '{safe_id}'"))),
    }
}

async fn feedback(State(state): State<ApiState>, body: Bytes) -> Result<Json<Value>, ApiError> {
    let request: FeedbackRequest = decode(body, RequestKind::Feedback)?;
    let decision_id = request.decision_id.clone();
    let home = state.home;
    let recorded = blocking(move || service::save_feedback(&home, &request)).await?;
    if !recorded {
        let message = format!("no decision '{}'", safe_echo(&decision_id));
        return Err(ApiError {
            status: StatusCode::NOT_FOUND,
            code: "not_found",
            message,
        });
    }
    Ok(Json(json!({"decision_id": decision_id, "recorded": true})))
}

async fn dry_run(State(state): State<ApiState>, body: Bytes) -> Result<Json<Value>, ApiError> {
    let request: DryRunRequest = decode(body, RequestKind::DryRun)?;
    let decision_id = request.decision_id.clone();
    let home = state.home;
    let result = blocking(move || service::execute_dry_run(&home, &request)).await?;
    result.map(Json).ok_or_else(|| ApiError {
        status: StatusCode::NOT_FOUND,
        code: "not_found",
        message: format!("no decision '{}'", safe_echo(&decision_id)),
    })
}

async fn not_found() -> ApiError {
    ApiError::not_found("Not Found")
}

async fn docs() -> Html<&'static str> {
    Html(
        "<!doctype html><html><head><title>AgentRouter OS API</title></head><body><h1>AgentRouter OS API</h1><p><a href=\"/openapi.json\">OpenAPI contract</a></p></body></html>",
    )
}

async fn openapi() -> Response {
    const DOCUMENT: &str = include_str!("../../../contracts/http/v1/openapi.json");
    ([(header::CONTENT_TYPE, "application/json")], DOCUMENT).into_response()
}
