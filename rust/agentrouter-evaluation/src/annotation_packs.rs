//! Blinded annotation pack operations mirrored from
//! `agentrouter.annotation.packs`.

use std::collections::BTreeSet;

use crate::annotation_schema::{Candidate, ItemLabels};

/// CPython's MT19937 seeding and `_randbelow`-based shuffle, so pack order is
/// stable across the Python and Rust implementations for integer seeds.
#[derive(Clone)]
pub(crate) struct PythonRandom {
    state: [u32; 624],
    index: usize,
}

impl PythonRandom {
    pub(crate) fn new(seed: &str) -> Result<Self, String> {
        let magnitude = seed.strip_prefix('-').unwrap_or(seed);
        if magnitude.is_empty() || !magnitude.bytes().all(|digit| digit.is_ascii_digit()) {
            return Err("seed must be a decimal integer".to_owned());
        }
        let mut digits = magnitude
            .bytes()
            .map(|digit| digit - b'0')
            .collect::<Vec<_>>();
        let mut words = Vec::new();
        while digits.iter().any(|digit| *digit != 0) {
            let mut remainder = 0_u64;
            for digit in &mut digits {
                let value = remainder * 10 + u64::from(*digit);
                *digit = (value / (1_u64 << 32)) as u8;
                remainder = value % (1_u64 << 32);
            }
            words.push(remainder as u32);
            let first_nonzero = digits
                .iter()
                .position(|digit| *digit != 0)
                .unwrap_or(digits.len());
            digits.drain(..first_nonzero);
        }
        if words.is_empty() {
            words.push(0);
        }
        Ok(Self::from_key(words))
    }

    fn from_key(key: Vec<u32>) -> Self {
        let mut rng = Self {
            state: [0; 624],
            index: 624,
        };
        rng.state[0] = 19_650_218;
        for i in 1..624 {
            rng.state[i] = 1_812_433_253_u32
                .wrapping_mul(rng.state[i - 1] ^ (rng.state[i - 1] >> 30))
                .wrapping_add(i as u32);
        }
        let mut i = 1;
        let mut j = 0;
        for _ in 0..624.max(key.len()) {
            rng.state[i] = (rng.state[i]
                ^ (rng.state[i - 1] ^ (rng.state[i - 1] >> 30)).wrapping_mul(1_664_525))
            .wrapping_add(key[j])
            .wrapping_add(j as u32);
            i += 1;
            j += 1;
            if i >= 624 {
                rng.state[0] = rng.state[623];
                i = 1;
            }
            if j >= key.len() {
                j = 0;
            }
        }
        for _ in 0..623 {
            rng.state[i] = (rng.state[i]
                ^ (rng.state[i - 1] ^ (rng.state[i - 1] >> 30)).wrapping_mul(1_566_083_941))
            .wrapping_sub(i as u32);
            i += 1;
            if i >= 624 {
                rng.state[0] = rng.state[623];
                i = 1;
            }
        }
        rng.state[0] = 0x8000_0000;
        rng
    }

    fn next_u32(&mut self) -> u32 {
        if self.index >= 624 {
            for i in 0..624 {
                let y = (self.state[i] & 0x8000_0000) | (self.state[(i + 1) % 624] & 0x7fff_ffff);
                self.state[i] = self.state[(i + 397) % 624]
                    ^ (y >> 1)
                    ^ if y & 1 == 0 { 0 } else { 0x9908_b0df };
            }
            self.index = 0;
        }
        let mut y = self.state[self.index];
        self.index += 1;
        y ^= y >> 11;
        y ^= (y << 7) & 0x9d2c_5680;
        y ^= (y << 15) & 0xefc6_0000;
        y ^= y >> 18;
        y
    }

    pub(crate) fn randbelow(&mut self, upper: usize) -> usize {
        let bits = usize::BITS - upper.leading_zeros();
        loop {
            let value = if bits <= 32 {
                (self.next_u32() >> (32 - bits)) as usize
            } else {
                let high = self.next_u32() as u64;
                let low = self.next_u32() as u64;
                (((high << 32) | low) >> (64 - bits)) as usize
            };
            if value < upper {
                return value;
            }
        }
    }
}

/// Draw indexes using Python `random.Random(seed).randrange(length)` semantics.
pub fn sample_indexes_python_seed(
    length: usize,
    draws: usize,
    seed: &str,
) -> Result<Vec<usize>, String> {
    if length == 0 && draws != 0 {
        return Err("cannot sample from an empty population".to_owned());
    }
    let mut rng = PythonRandom::new(seed)?;
    Ok((0..draws).map(|_| rng.randbelow(length)).collect())
}

pub fn shuffle_python_seed<T>(values: &mut [T], seed: &str) -> Result<(), String> {
    let mut rng = PythonRandom::new(seed)?;
    for i in (1..values.len()).rev() {
        let j = rng.randbelow(i + 1);
        values.swap(i, j);
    }
    Ok(())
}

pub fn build_pack(candidates: &[Candidate], seed: &str) -> Result<Vec<Candidate>, String> {
    let mut ordered = candidates.to_vec();
    shuffle_python_seed(&mut ordered, seed)?;
    Ok(ordered
        .into_iter()
        .map(|candidate| Candidate {
            id: candidate.id,
            prompt: candidate.prompt,
            category: candidate.category,
            source: candidate.source,
            template: None,
            notes: None,
        })
        .collect())
}

pub fn labelled_ids(labels: &[ItemLabels]) -> BTreeSet<String> {
    labels
        .iter()
        .map(|item| item.candidate_id.clone())
        .collect()
}

pub fn pending(candidates: &[Candidate], done: &[ItemLabels]) -> Vec<Candidate> {
    let seen = labelled_ids(done);
    candidates
        .iter()
        .filter(|candidate| !seen.contains(&candidate.id))
        .cloned()
        .collect()
}

pub fn progress(candidates: &[Candidate], done: &[ItemLabels]) -> (usize, usize, usize) {
    let total = candidates.len();
    let candidate_ids = candidates
        .iter()
        .map(|candidate| candidate.id.as_str())
        .collect::<BTreeSet<_>>();
    let complete = labelled_ids(done)
        .iter()
        .filter(|id| candidate_ids.contains(id.as_str()))
        .count();
    (total, complete, total - complete)
}

pub fn merge_by_candidate(label_sets: &[Vec<ItemLabels>]) -> Vec<ItemLabels> {
    let mut merged = Vec::<ItemLabels>::new();
    for item in label_sets.iter().flatten() {
        if let Some(existing) = merged
            .iter_mut()
            .find(|existing| existing.candidate_id == item.candidate_id)
        {
            existing.labels.extend(item.labels.clone());
        } else {
            merged.push(item.clone());
        }
    }
    merged
}

fn needs_adjudication(item: &ItemLabels) -> bool {
    if item.labels.len() < 2 {
        return true;
    }
    if item.labels.iter().all(|label| label.abstain) {
        return false;
    }
    let has_abstention = item.labels.iter().any(|label| label.abstain);
    let mut bands = item
        .labels
        .iter()
        .filter(|label| !label.abstain)
        .filter_map(|label| label.band);
    let first = bands.next();
    has_abstention || first.is_none() || bands.any(|band| Some(band) != first)
}

pub fn disagreement_items(label_sets: &[Vec<ItemLabels>]) -> Vec<ItemLabels> {
    merge_by_candidate(label_sets)
        .into_iter()
        .filter(needs_adjudication)
        .collect()
}

pub fn adjudication_candidates(label_sets: &[Vec<ItemLabels>]) -> Vec<Candidate> {
    disagreement_items(label_sets)
        .into_iter()
        .map(|item| Candidate {
            id: item.candidate_id,
            prompt: item.prompt,
            category: item.category,
            source: "curated".to_owned(),
            template: None,
            notes: None,
        })
        .collect()
}

fn csv_field(value: &str) -> String {
    if value.contains([',', '"', '\n', '\r']) {
        format!("\"{}\"", value.replace('"', "\"\""))
    } else {
        value.to_owned()
    }
}

fn python_float(value: f64) -> String {
    if value != 0.0 && value.abs() < 0.0001 {
        let debug = format!("{value:?}");
        if let Some((mantissa, exponent)) = debug.split_once('e') {
            let exponent = exponent
                .parse::<i32>()
                .expect("Rust emits numeric exponent");
            return format!("{mantissa}e{exponent:+03}");
        }
    }
    if value.fract() == 0.0 {
        format!("{value:.1}")
    } else {
        value.to_string()
    }
}

pub fn labels_to_csv(labels: &[ItemLabels]) -> String {
    let mut csv = String::from(
        "candidate_id,prompt,category,annotator,band,abstain,rationale,confidence\r\n",
    );
    for item in labels {
        for label in &item.labels {
            let band = label
                .band
                .map(|band| serde_json::to_value(band).expect("band serializes"))
                .and_then(|value| value.as_str().map(str::to_owned))
                .unwrap_or_default();
            let confidence = python_float(label.confidence);
            let fields = [
                item.candidate_id.as_str(),
                item.prompt.as_str(),
                item.category.as_str(),
                label.annotator.as_str(),
                band.as_str(),
                if label.abstain { "True" } else { "False" },
                label.rationale.as_str(),
                confidence.as_str(),
            ];
            csv.push_str(
                &fields
                    .iter()
                    .map(|field| csv_field(field))
                    .collect::<Vec<_>>()
                    .join(","),
            );
            csv.push_str("\r\n");
        }
    }
    csv
}
