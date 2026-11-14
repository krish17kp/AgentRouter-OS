//! Bounded process-local rate limiting and idempotency primitives mirrored
//! from `agentrouter.server.limits`.
//!
//! These primitives intentionally do not claim distributed consistency. A
//! multi-process server needs shared state in its HTTP integration layer.

use std::collections::{HashMap, VecDeque};
use std::env;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Mutex, MutexGuard};
use std::time::Instant;

pub const RATE_LIMIT_ENV: &str = "AGENTROUTER_RATE_LIMIT";
pub const RATE_WINDOW_ENV: &str = "AGENTROUTER_RATE_WINDOW";
pub const IDEMPOTENCY_TTL_ENV: &str = "AGENTROUTER_IDEMPOTENCY_TTL";
pub const DEFAULT_WINDOW: i128 = 60;
pub const DEFAULT_IDEMPOTENCY_TTL: i128 = 300;
pub const MAX_ENTRIES: usize = 10_000;
/// Aggregate response-body memory retained by an idempotency cache.
pub const MAX_CACHE_BYTES: usize = 16 * 1024 * 1024;

pub const RATE_EXEMPT_PATHS: [&str; 2] = ["/health", "/ready"];

pub fn client_key(api_key: Option<&str>, host: Option<&str>) -> String {
    match api_key.filter(|value| !value.is_empty()) {
        Some(api_key) => format!("key:{api_key}"),
        None => format!(
            "ip:{}",
            host.filter(|value| !value.is_empty()).unwrap_or("unknown")
        ),
    }
}

fn lock<T>(mutex: &Mutex<T>) -> MutexGuard<'_, T> {
    mutex
        .lock()
        .unwrap_or_else(std::sync::PoisonError::into_inner)
}

fn python_int_env(name: &str, default: i128) -> i128 {
    let Ok(value) = env::var(name) else {
        return default;
    };
    let value = value.trim();
    let (sign, digits) = if let Some(digits) = value.strip_prefix('-') {
        (-1_i128, digits)
    } else if let Some(digits) = value.strip_prefix('+') {
        (1_i128, digits)
    } else {
        (1_i128, value)
    };
    let bytes = digits.as_bytes();
    if bytes.is_empty()
        || !bytes.iter().enumerate().all(|(index, byte)| {
            byte.is_ascii_digit()
                || (*byte == b'_'
                    && index > 0
                    && index + 1 < bytes.len()
                    && bytes[index - 1].is_ascii_digit()
                    && bytes[index + 1].is_ascii_digit())
        })
    {
        return default;
    }
    let normalized = digits.replace('_', "");
    match normalized.parse::<i128>() {
        Ok(number) => number.saturating_mul(sign),
        Err(_) if sign < 0 => i128::MIN,
        Err(_) => i128::MAX,
    }
}

#[derive(Clone, Copy)]
struct Bucket {
    started_at: f64,
    count: u64,
}

#[derive(Default)]
struct RateState {
    buckets: HashMap<String, Bucket>,
    insertion_order: VecDeque<String>,
}

/// Fixed-window counter. A non-positive limit disables counting.
pub struct RateLimiter {
    limit: Option<i128>,
    window: Option<i128>,
    started: Instant,
    state: Mutex<RateState>,
}

impl RateLimiter {
    pub fn new(limit: Option<i128>, window: Option<i128>) -> Self {
        Self {
            limit,
            window,
            started: Instant::now(),
            state: Mutex::new(RateState::default()),
        }
    }

    fn limit(&self) -> i128 {
        self.limit
            .unwrap_or_else(|| python_int_env(RATE_LIMIT_ENV, 0))
    }

    fn window(&self) -> i128 {
        self.window
            .unwrap_or_else(|| python_int_env(RATE_WINDOW_ENV, DEFAULT_WINDOW))
    }

    pub fn check(&self, key: &str) -> (bool, i128) {
        self.check_at(key, self.started.elapsed().as_secs_f64())
    }

    /// Deterministic-clock seam used by differential tests and offline callers.
    pub fn check_at(&self, key: &str, now: f64) -> (bool, i128) {
        let limit = self.limit();
        if limit <= 0 {
            return (true, 0);
        }
        let window = self.window().max(1) as f64;
        let mut state = lock(&self.state);
        if !state.buckets.contains_key(key) {
            state.insertion_order.push_back(key.to_owned());
            state.buckets.insert(
                key.to_owned(),
                Bucket {
                    started_at: now,
                    count: 0,
                },
            );
        }
        let bucket = state.buckets.get_mut(key).expect("bucket inserted above");
        if now - bucket.started_at >= window {
            bucket.started_at = now;
            bucket.count = 0;
        }
        bucket.count = bucket.count.saturating_add(1);
        let count = bucket.count;
        let started_at = bucket.started_at;

        if state.buckets.len() > MAX_ENTRIES {
            state
                .buckets
                .retain(|_, current| now - current.started_at < window);
            let live_keys: std::collections::HashSet<String> =
                state.buckets.keys().cloned().collect();
            state
                .insertion_order
                .retain(|candidate| live_keys.contains(candidate));
            while state.buckets.len() > MAX_ENTRIES {
                if let Some(oldest) = state.insertion_order.pop_front() {
                    state.buckets.remove(&oldest);
                } else {
                    break;
                }
            }
        }

        if i128::from(count) > limit {
            let remaining = (window - (now - started_at)).trunc();
            (false, (remaining as i128).max(1))
        } else {
            (true, 0)
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct CachedResponse {
    pub status: u16,
    pub body: Vec<u8>,
    pub media_type: Option<String>,
}

#[derive(Default)]
struct CacheState {
    values: HashMap<String, (f64, CachedResponse)>,
    insertion_order: VecDeque<String>,
    total_bytes: usize,
}

struct FlightEntry {
    active_users: AtomicUsize,
    gate: Mutex<()>,
}

/// TTL response cache with per-key single-flight work serialization.
pub struct IdempotencyCache {
    ttl: Option<i128>,
    started: Instant,
    state: Mutex<CacheState>,
    flights: Mutex<HashMap<String, Arc<FlightEntry>>>,
}

struct FlightLease<'a> {
    cache: &'a IdempotencyCache,
    key: String,
    entry: Arc<FlightEntry>,
}

impl Drop for FlightLease<'_> {
    fn drop(&mut self) {
        let mut flights = lock(&self.cache.flights);
        if self.entry.active_users.fetch_sub(1, Ordering::AcqRel) == 1
            && flights
                .get(&self.key)
                .is_some_and(|entry| Arc::ptr_eq(entry, &self.entry))
        {
            flights.remove(&self.key);
        }
    }
}

impl IdempotencyCache {
    pub fn new(ttl: Option<i128>) -> Self {
        Self {
            ttl,
            started: Instant::now(),
            state: Mutex::new(CacheState::default()),
            flights: Mutex::new(HashMap::new()),
        }
    }

    fn ttl(&self) -> i128 {
        self.ttl
            .unwrap_or_else(|| python_int_env(IDEMPOTENCY_TTL_ENV, DEFAULT_IDEMPOTENCY_TTL))
    }

    fn acquire_flight(&self, key: &str) -> FlightLease<'_> {
        let mut flights = lock(&self.flights);
        let entry = flights
            .entry(key.to_owned())
            .or_insert_with(|| {
                Arc::new(FlightEntry {
                    active_users: AtomicUsize::new(0),
                    gate: Mutex::new(()),
                })
            })
            .clone();
        entry.active_users.fetch_add(1, Ordering::AcqRel);
        FlightLease {
            cache: self,
            key: key.to_owned(),
            entry,
        }
    }

    pub fn get(&self, key: &str) -> Option<CachedResponse> {
        self.get_at(key, self.started.elapsed().as_secs_f64())
    }

    pub fn get_at(&self, key: &str, now: f64) -> Option<CachedResponse> {
        let mut state = lock(&self.state);
        let expired = state
            .values
            .get(key)
            .is_some_and(|(stored_at, _)| now - stored_at > self.ttl() as f64);
        if expired {
            if let Some((_, response)) = state.values.remove(key) {
                state.total_bytes = state.total_bytes.saturating_sub(response.body.len());
            }
            state.insertion_order.retain(|candidate| candidate != key);
            return None;
        }
        state.values.get(key).map(|(_, response)| response.clone())
    }

    pub fn put(&self, key: &str, response: CachedResponse) {
        self.put_at(key, response, self.started.elapsed().as_secs_f64());
    }

    pub fn put_at(&self, key: &str, response: CachedResponse, now: f64) {
        let response_bytes = response.body.len();
        if response_bytes > MAX_CACHE_BYTES {
            return;
        }
        let mut state = lock(&self.state);
        if let Some((_, previous)) = state.values.remove(key) {
            state.total_bytes = state.total_bytes.saturating_sub(previous.body.len());
            state.insertion_order.retain(|candidate| candidate != key);
        }

        let needs_cleanup = state.values.len() >= MAX_ENTRIES
            || state.total_bytes.saturating_add(response_bytes) > MAX_CACHE_BYTES;
        if needs_cleanup {
            let ttl = self.ttl() as f64;
            let mut retained_bytes: usize = 0;
            state.values.retain(|_, (stored_at, cached)| {
                let keep = now - *stored_at <= ttl;
                if keep {
                    retained_bytes = retained_bytes.saturating_add(cached.body.len());
                }
                keep
            });
            state.total_bytes = retained_bytes;
            let live_keys: std::collections::HashSet<String> =
                state.values.keys().cloned().collect();
            state
                .insertion_order
                .retain(|candidate| live_keys.contains(candidate));
        }

        while state.values.len() >= MAX_ENTRIES
            || state.total_bytes.saturating_add(response_bytes) > MAX_CACHE_BYTES
        {
            let Some(oldest) = state.insertion_order.pop_front() else {
                break;
            };
            if let Some((_, removed)) = state.values.remove(&oldest) {
                state.total_bytes = state.total_bytes.saturating_sub(removed.body.len());
            }
        }

        state.insertion_order.push_back(key.to_owned());
        state.total_bytes = state.total_bytes.saturating_add(response_bytes);
        state.values.insert(key.to_owned(), (now, response));
    }

    /// Serialize work by key, replay a cached response, and cache successful
    /// (2xx) responses. Errors and non-2xx responses remain uncached.
    pub fn get_or_compute<E>(
        &self,
        key: &str,
        operation: impl FnOnce() -> Result<CachedResponse, E>,
    ) -> Result<CachedResponse, E> {
        self.get_or_compute_at(key, self.started.elapsed().as_secs_f64(), operation)
    }

    pub fn get_or_compute_at<E>(
        &self,
        key: &str,
        now: f64,
        operation: impl FnOnce() -> Result<CachedResponse, E>,
    ) -> Result<CachedResponse, E> {
        let lease = self.acquire_flight(key);
        let _guard = lock(&lease.entry.gate);
        if let Some(response) = self.get_at(key, now) {
            return Ok(response);
        }
        let response = operation()?;
        if (200..300).contains(&response.status) {
            self.put_at(key, response.clone(), now);
        }
        Ok(response)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};
    use std::thread;
    use std::time::Duration;

    fn response(status: u16, body: &[u8]) -> CachedResponse {
        CachedResponse {
            status,
            body: body.to_vec(),
            media_type: Some("application/json".to_owned()),
        }
    }

    #[test]
    fn client_key_matches_python_precedence_and_empty_values() {
        assert_eq!(client_key(Some("secret"), Some("1.2.3.4")), "key:secret");
        assert_eq!(client_key(Some(""), Some("1.2.3.4")), "ip:1.2.3.4");
        assert_eq!(client_key(None, Some("")), "ip:unknown");
    }

    #[test]
    fn rate_limiter_uses_independent_fixed_windows_and_retry_after() {
        let limiter = RateLimiter::new(Some(2), Some(10));
        assert_eq!(limiter.check_at("a", 100.0), (true, 0));
        assert_eq!(limiter.check_at("a", 101.0), (true, 0));
        assert_eq!(limiter.check_at("a", 102.0), (false, 8));
        assert_eq!(limiter.check_at("b", 102.0), (true, 0));
        assert_eq!(limiter.check_at("a", 110.0), (true, 0));
    }

    #[test]
    fn disabled_rate_limit_is_a_noop() {
        let limiter = RateLimiter::new(Some(0), Some(1));
        for _ in 0..100 {
            assert_eq!(limiter.check_at("a", 0.0), (true, 0));
        }
    }

    #[test]
    fn cache_expires_only_after_ttl_and_preserves_response_fields() {
        let cache = IdempotencyCache::new(Some(5));
        let expected = response(201, b"body");
        cache.put_at("key", expected.clone(), 10.0);
        assert_eq!(cache.get_at("key", 15.0), Some(expected.clone()));
        assert_eq!(cache.get_at("key", 15.01), None);
    }

    #[test]
    fn non_successful_responses_are_not_cached() {
        let cache = IdempotencyCache::new(Some(5));
        let result = cache
            .get_or_compute_at("key", 10.0, || Ok::<_, ()>(response(422, b"bad")))
            .unwrap();
        assert_eq!(result.status, 422);
        assert_eq!(cache.get_at("key", 10.0), None);
    }

    #[test]
    fn concurrent_same_key_requests_run_work_once() {
        let cache = Arc::new(IdempotencyCache::new(Some(60)));
        let calls = Arc::new(AtomicUsize::new(0));
        let threads: Vec<_> = (0..8)
            .map(|_| {
                let cache = Arc::clone(&cache);
                let calls = Arc::clone(&calls);
                thread::spawn(move || {
                    cache
                        .get_or_compute("same", || {
                            calls.fetch_add(1, Ordering::SeqCst);
                            thread::sleep(Duration::from_millis(10));
                            Ok::<_, ()>(response(200, b"shared"))
                        })
                        .unwrap()
                })
            })
            .collect();
        for thread in threads {
            assert_eq!(thread.join().unwrap(), response(200, b"shared"));
        }
        assert_eq!(calls.load(Ordering::SeqCst), 1);
        assert!(lock(&cache.flights).is_empty());
    }

    #[test]
    fn rate_and_idempotency_stores_stay_within_the_entry_cap() {
        let limiter = RateLimiter::new(Some(100), Some(10_000));
        let cache = IdempotencyCache::new(Some(10_000));
        for index in 0..=MAX_ENTRIES {
            let key = format!("key-{index}");
            limiter.check_at(&key, 0.0);
            cache.put_at(&key, response(200, b"ok"), 0.0);
        }
        assert_eq!(lock(&limiter.state).buckets.len(), MAX_ENTRIES);
        assert_eq!(lock(&cache.state).values.len(), MAX_ENTRIES);
        assert_eq!(cache.get_at("key-0", 0.0), None);
        assert_eq!(cache.get_at("key-1", 0.0), Some(response(200, b"ok")));
    }

    #[test]
    fn idempotency_cache_stays_within_aggregate_body_limit() {
        let cache = IdempotencyCache::new(Some(60));
        let body = vec![b'x'; MAX_CACHE_BYTES / 2];
        cache.put("first", response(200, &body));
        let second_body = vec![b'y'; MAX_CACHE_BYTES / 2 + 1];
        cache.put("second", response(200, &second_body));
        assert!(lock(&cache.state).total_bytes <= MAX_CACHE_BYTES);
        assert_eq!(cache.get("first"), None);
        assert_eq!(
            cache.get("second").map(|cached| cached.body.len()),
            Some(second_body.len())
        );

        cache.put("too-large", response(200, &vec![b'x'; MAX_CACHE_BYTES + 1]));
        assert_eq!(cache.get("too-large"), None);
    }
}
