//! Load and soak measurements compatible with `agentrouter.reliability`.
//!
//! Latency and resource measurements are reports only. Correctness signals
//! (unexpected HTTP statuses, server errors, and transport failures) remain
//! suitable for release gates; timing thresholds deliberately do not.

use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::Path;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

const EXPECTED_STATUSES: &[u16] = &[200, 201, 404, 409, 422, 429];

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Request {
    pub method: String,
    pub path: String,
    pub body: Option<Value>,
}

impl Request {
    pub fn get(path: impl Into<String>) -> Self {
        Self {
            method: "GET".into(),
            path: path.into(),
            body: None,
        }
    }

    pub fn post(path: impl Into<String>, body: Value) -> Self {
        Self {
            method: "POST".into(),
            path: path.into(),
            body: Some(body),
        }
    }
}

pub type RequestFactory = Arc<dyn Fn(usize) -> Request + Send + Sync>;

#[derive(Clone)]
pub struct LoadSpec {
    pub total: usize,
    pub workers: usize,
    pub timeout_seconds: f64,
    pub request: Option<RequestFactory>,
}

impl Default for LoadSpec {
    fn default() -> Self {
        Self {
            total: 200,
            workers: 32,
            timeout_seconds: 30.0,
            request: None,
        }
    }
}

impl LoadSpec {
    pub fn build(&self, index: usize) -> Request {
        self.request.as_ref().map_or_else(
            || {
                Request::post(
                    "/v1/route",
                    json!({"task": format!("refactor module {index}")}),
                )
            },
            |factory| factory(index),
        )
    }
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct LoadOutcome {
    pub statuses: BTreeMap<u16, usize>,
    pub transport_errors: BTreeMap<String, usize>,
    pub latencies_ms: Vec<f64>,
    pub elapsed_seconds: f64,
    pub request_ids: Vec<String>,
}

impl LoadOutcome {
    pub fn ok(&self) -> usize {
        self.statuses.get(&200).copied().unwrap_or_default()
    }

    pub fn unexpected(&self) -> BTreeMap<u16, usize> {
        self.statuses
            .iter()
            .filter(|(status, _)| !EXPECTED_STATUSES.contains(status))
            .map(|(status, count)| (*status, *count))
            .collect()
    }

    pub fn server_errors(&self) -> usize {
        self.statuses
            .iter()
            .filter(|(status, _)| (500..600).contains(*status))
            .map(|(_, count)| count)
            .sum()
    }

    pub fn throughput(&self) -> f64 {
        if self.elapsed_seconds == 0.0 {
            0.0
        } else {
            self.latencies_ms.len() as f64 / self.elapsed_seconds
        }
    }

    pub fn percentile(&self, percentile: f64) -> f64 {
        if self.latencies_ms.is_empty() {
            return 0.0;
        }
        let mut values = self.latencies_ms.clone();
        values.sort_by(f64::total_cmp);
        let position = (percentile / 100.0) * (values.len() - 1) as f64;
        let index = (position.round_ties_even() as usize).min(values.len() - 1);
        values[index]
    }

    pub fn as_dict(&self) -> Value {
        let mean = if self.latencies_ms.is_empty() {
            0.0
        } else {
            self.latencies_ms.iter().sum::<f64>() / self.latencies_ms.len() as f64
        };
        let request_count: usize =
            self.statuses.values().sum::<usize>() + self.transport_errors.values().sum::<usize>();
        let distinct_request_ids: BTreeSet<_> = self.request_ids.iter().collect();
        json!({
            "requests": request_count,
            "statuses": self.statuses,
            "transport_errors": self.transport_errors,
            "unexpected_statuses": self.unexpected(),
            "server_errors": self.server_errors(),
            "distinct_request_ids": distinct_request_ids.len(),
            "timing_indicative_only": {
                "elapsed_seconds": round_to(self.elapsed_seconds, 3),
                "throughput_per_second": round_to(self.throughput(), 1),
                "p50_ms": round_to(self.percentile(50.0), 1),
                "p95_ms": round_to(self.percentile(95.0), 1),
                "p99_ms": round_to(self.percentile(99.0), 1),
                "mean_ms": round_to(mean, 1),
            }
        })
    }
}

/// Send a fixed number of requests from a bounded pool of worker threads.
/// Timing is recorded; the function never applies a latency pass/fail threshold.
pub fn run_load(url: &str, spec: &LoadSpec) -> LoadOutcome {
    let next = AtomicUsize::new(0);
    let outcome = Arc::new(Mutex::new(LoadOutcome::default()));
    let workers = spec.workers.min(spec.total);
    let timeout = Duration::from_secs_f64(valid_timeout(spec.timeout_seconds));
    let started = Instant::now();

    thread::scope(|scope| {
        for _ in 0..workers {
            let outcome = Arc::clone(&outcome);
            let next = &next;
            scope.spawn(move || {
                let agent = ureq::AgentBuilder::new()
                    .timeout(timeout)
                    // Match httpx's default and avoid unexpectedly sending a
                    // load request to a redirect target.
                    .redirects(0)
                    .build();
                loop {
                    let index = next.fetch_add(1, Ordering::Relaxed);
                    if index >= spec.total {
                        break;
                    }
                    let request = spec.build(index);
                    let request_url = format!("{url}{}", request.path);
                    let request_started = Instant::now();
                    let mut builder = agent.request(&request.method, &request_url);
                    if request.body.is_some() {
                        builder = builder.set("Content-Type", "application/json");
                    }
                    let response = match request.body {
                        Some(body) => builder.send_string(&body.to_string()),
                        None => builder.call(),
                    };
                    let mut outcome = outcome.lock().expect("load outcome mutex poisoned");
                    match response {
                        Ok(response) => record_response(
                            &mut outcome,
                            response.status(),
                            response.header("X-Request-ID"),
                            request_started.elapsed(),
                        ),
                        Err(ureq::Error::Status(status, response)) => record_response(
                            &mut outcome,
                            status,
                            response.header("X-Request-ID"),
                            request_started.elapsed(),
                        ),
                        Err(ureq::Error::Transport(_)) => {
                            *outcome
                                .transport_errors
                                .entry("TransportError".into())
                                .or_default() += 1;
                        }
                    }
                }
            });
        }
    });

    let mut outcome = Arc::try_unwrap(outcome)
        .expect("all load workers have exited")
        .into_inner()
        .expect("load outcome mutex poisoned");
    outcome.elapsed_seconds = started.elapsed().as_secs_f64();
    outcome
}

fn record_response(
    outcome: &mut LoadOutcome,
    status: u16,
    request_id: Option<&str>,
    elapsed: Duration,
) {
    *outcome.statuses.entry(status).or_default() += 1;
    outcome.latencies_ms.push(elapsed.as_secs_f64() * 1000.0);
    if let Some(request_id) = request_id {
        outcome.request_ids.push(request_id.to_string());
    }
}

fn valid_timeout(timeout_seconds: f64) -> f64 {
    if timeout_seconds.is_finite() && timeout_seconds > 0.0 {
        timeout_seconds
    } else {
        0.001
    }
}

fn round_to(value: f64, places: i32) -> f64 {
    let scale = 10_f64.powi(places);
    (value * scale).round_ties_even() / scale
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Sample {
    pub at_seconds: f64,
    pub rss_kb: i64,
    pub open_fds: i64,
    pub db_bytes: u64,
    pub wal_bytes: u64,
    pub ok: usize,
    pub server_errors: usize,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct SoakResult {
    pub samples: Vec<Sample>,
    pub total_ok: usize,
    pub total_server_errors: usize,
    pub transport_errors: BTreeMap<String, usize>,
}

impl SoakResult {
    pub fn growth(&self, attribute: &str) -> (i64, i64, f64) {
        if self.samples.is_empty() {
            return (0, 0, 0.0);
        }
        let measure = |sample: &Sample| match attribute {
            "rss_kb" => sample.rss_kb,
            "open_fds" => sample.open_fds,
            "db_bytes" => sample.db_bytes.min(i64::MAX as u64) as i64,
            "wal_bytes" => sample.wal_bytes.min(i64::MAX as u64) as i64,
            "ok" => sample.ok.min(i64::MAX as usize) as i64,
            "server_errors" => sample.server_errors.min(i64::MAX as usize) as i64,
            _ => 0,
        };
        let first = measure(&self.samples[0]);
        let last = measure(self.samples.last().expect("samples is non-empty"));
        let ratio = if first == 0 {
            0.0
        } else {
            last as f64 / first as f64
        };
        (first, last, ratio)
    }

    pub fn as_dict(&self) -> Value {
        let trend = |attribute: &str| {
            let (first, last, ratio) = self.growth(attribute);
            json!({"first": first, "last": last, "ratio": round_to(ratio, 2)})
        };
        json!({
            "cycles": self.samples.len(),
            "total_ok": self.total_ok,
            "total_server_errors": self.total_server_errors,
            "transport_errors": self.transport_errors,
            "resource_trend_indicative_only": {
                "rss_kb": trend("rss_kb"),
                "open_fds": trend("open_fds"),
                "db_bytes": trend("db_bytes"),
            },
            "samples": self.samples,
        })
    }
}

/// Run repeated batches against an already-running API process and sample its
/// local database/WAL files. Resource trends and latency are indicative only.
pub fn soak(url: &str, home: &Path, seconds: f64, workers: usize, batch: usize) -> SoakResult {
    let mut result = SoakResult::default();
    let started = Instant::now();
    while started.elapsed().as_secs_f64() < seconds {
        let outcome = run_load(
            url,
            &LoadSpec {
                total: batch,
                workers,
                ..LoadSpec::default()
            },
        );
        let ok = outcome.ok();
        let server_errors = outcome.server_errors();
        result.total_ok += ok;
        result.total_server_errors += server_errors;
        for (name, count) in outcome.transport_errors {
            *result.transport_errors.entry(name).or_default() += count;
        }
        result.samples.push(Sample {
            at_seconds: round_to(started.elapsed().as_secs_f64(), 1),
            rss_kb: rss_kb(),
            open_fds: open_fds(),
            db_bytes: file_size(&home.join("agentrouter.db")),
            wal_bytes: file_size(&home.join("agentrouter.db-wal")),
            ok,
            server_errors,
        });
    }
    result
}

fn file_size(path: &Path) -> u64 {
    fs::metadata(path)
        .map(|metadata| metadata.len())
        .unwrap_or_default()
}

fn open_fds() -> i64 {
    let path = format!("/proc/{}/fd", std::process::id());
    fs::read_dir(path)
        .map(|entries| entries.count() as i64)
        .unwrap_or(-1)
}

fn rss_kb() -> i64 {
    #[cfg(unix)]
    {
        let mut usage = std::mem::MaybeUninit::<libc::rusage>::uninit();
        // SAFETY: getrusage initializes the supplied rusage structure when it
        // returns zero; the value is read only after that success check.
        let result = unsafe { libc::getrusage(libc::RUSAGE_SELF, usage.as_mut_ptr()) };
        if result == 0 {
            // SAFETY: guarded by the successful getrusage call above.
            // `ru_maxrss` is `c_long`; conversion is needed on 32-bit Unix
            // even though Clippy sees an identity conversion on 64-bit Linux.
            #[allow(clippy::useless_conversion)]
            return unsafe { usage.assume_init() }
                .ru_maxrss
                .try_into()
                .unwrap_or(-1);
        }
    }
    -1
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn load_summary_preserves_correctness_and_indicative_timing_fields() {
        let outcome = LoadOutcome {
            statuses: BTreeMap::from([(200, 8), (500, 1)]),
            transport_errors: BTreeMap::from([("timeout".into(), 1)]),
            latencies_ms: vec![1.0, 2.0, 3.0, 4.0],
            elapsed_seconds: 2.0,
            request_ids: vec!["a".into(), "a".into(), "b".into()],
        };
        assert_eq!(outcome.ok(), 8);
        assert_eq!(outcome.server_errors(), 1);
        assert_eq!(outcome.unexpected(), BTreeMap::from([(500, 1)]));
        assert_eq!(outcome.percentile(50.0), 3.0);
        assert_eq!(outcome.as_dict()["requests"], 10);
        assert_eq!(outcome.as_dict()["distinct_request_ids"], 2);
        assert_eq!(outcome.as_dict()["timing_indicative_only"]["p50_ms"], 3.0);
    }

    #[test]
    fn soak_growth_matches_empty_zero_and_positive_baselines() {
        let empty = SoakResult::default();
        assert_eq!(empty.growth("rss_kb"), (0, 0, 0.0));
        let result = SoakResult {
            samples: vec![sample(10, 100), sample(15, 250)],
            ..SoakResult::default()
        };
        assert_eq!(result.growth("rss_kb"), (10, 15, 1.5));
        assert_eq!(result.growth("db_bytes"), (100, 250, 2.5));
        assert_eq!(result.as_dict()["cycles"], 2);
    }

    fn sample(rss_kb: i64, db_bytes: u64) -> Sample {
        Sample {
            at_seconds: 1.0,
            rss_kb,
            open_fds: 4,
            db_bytes,
            wal_bytes: 0,
            ok: 1,
            server_errors: 0,
        }
    }
}
