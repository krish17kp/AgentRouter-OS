//! Duplicate and cross-split leakage checks mirrored from
//! `agentrouter.annotation.dedup`.

use std::collections::{HashMap, HashSet};

use agentrouter_routing::round_half_even;
use serde::Serialize;

pub const NEAR_THRESHOLD: f64 = 0.8;

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Duplicate {
    pub left: String,
    pub right: String,
    pub kind: String,
    pub score: f64,
}

pub fn normalize(prompt: &str) -> String {
    let mut output = String::new();
    let mut pending_space = false;
    for lowered in prompt.chars().flat_map(char::to_lowercase) {
        if lowered.is_whitespace() {
            pending_space = !output.is_empty();
        } else if lowered.is_ascii_lowercase() || lowered.is_ascii_digit() {
            if pending_space {
                output.push(' ');
                pending_space = false;
            }
            output.push(lowered);
        } else {
            pending_space = !output.is_empty();
        }
    }
    output
}

fn shingles(prompt: &str) -> HashSet<String> {
    let words: Vec<_> = normalize(prompt)
        .split_whitespace()
        .map(str::to_owned)
        .collect();
    if words.len() < 3 {
        return if words.is_empty() {
            HashSet::new()
        } else {
            [words.join(" ")].into_iter().collect()
        };
    }
    words.windows(3).map(|window| window.join(" ")).collect()
}

fn shingle_jaccard(left: &str, right: &str) -> f64 {
    let a = shingles(left);
    let b = shingles(right);
    if a.is_empty() && b.is_empty() {
        return 1.0;
    }
    if a.is_empty() || b.is_empty() {
        return 0.0;
    }
    let intersection = a.intersection(&b).count();
    intersection as f64 / (a.len() + b.len() - intersection) as f64
}

fn longest_match(
    a: &[char],
    b: &[char],
    alo: usize,
    ahi: usize,
    blo: usize,
    bhi: usize,
) -> (usize, usize, usize) {
    let mut b2j: HashMap<char, Vec<usize>> = HashMap::new();
    for (j, character) in b.iter().enumerate().take(bhi).skip(blo) {
        b2j.entry(*character).or_default().push(j);
    }
    if bhi - blo >= 200 {
        let popular_limit = (bhi - blo) / 100 + 1;
        b2j.retain(|_, indices| indices.len() <= popular_limit);
    }
    let mut best_i = alo;
    let mut best_j = blo;
    let mut best_size = 0;
    let mut previous = HashMap::<usize, usize>::new();
    for (i, character) in a.iter().enumerate().take(ahi).skip(alo) {
        let mut current = HashMap::<usize, usize>::new();
        if let Some(indices) = b2j.get(character) {
            for &j in indices {
                let prior = j
                    .checked_sub(1)
                    .and_then(|previous_j| previous.get(&previous_j))
                    .copied()
                    .unwrap_or(0);
                let size = prior + 1;
                current.insert(j, size);
                if size > best_size {
                    best_i = i + 1 - size;
                    best_j = j + 1 - size;
                    best_size = size;
                }
            }
        }
        previous = current;
    }
    while best_i > alo && best_j > blo && a[best_i - 1] == b[best_j - 1] {
        best_i -= 1;
        best_j -= 1;
        best_size += 1;
    }
    while best_i + best_size < ahi
        && best_j + best_size < bhi
        && a[best_i + best_size] == b[best_j + best_size]
    {
        best_size += 1;
    }
    (best_i, best_j, best_size)
}

fn sequence_ratio(left: &str, right: &str) -> f64 {
    let a: Vec<_> = left.chars().collect();
    let b: Vec<_> = right.chars().collect();
    if a.is_empty() && b.is_empty() {
        return 1.0;
    }
    let mut queue = vec![(0, a.len(), 0, b.len())];
    let mut matches = Vec::new();
    while let Some((alo, ahi, blo, bhi)) = queue.pop() {
        let (i, j, size) = longest_match(&a, &b, alo, ahi, blo, bhi);
        if size > 0 {
            matches.push((i, j, size));
            if alo < i && blo < j {
                queue.push((alo, i, blo, j));
            }
            if i + size < ahi && j + size < bhi {
                queue.push((i + size, ahi, j + size, bhi));
            }
        }
    }
    matches.sort_unstable();
    let mut matching = 0;
    let mut last_a = 0;
    let mut last_b = 0;
    let mut last_size = 0;
    for (i, j, size) in matches {
        if last_a + last_size == i && last_b + last_size == j {
            last_size += size;
        } else {
            matching += last_size;
            last_a = i;
            last_b = j;
            last_size = size;
        }
    }
    matching += last_size;
    2.0 * matching as f64 / (a.len() + b.len()) as f64
}

pub fn similarity(left: &str, right: &str) -> f64 {
    let a = normalize(left);
    let b = normalize(right);
    shingle_jaccard(left, right).max(sequence_ratio(&a, &b))
}

fn find_root(parent: &mut [usize], index: usize) -> usize {
    if parent[index] != index {
        parent[index] = find_root(parent, parent[index]);
    }
    parent[index]
}

pub fn cluster(prompts: &[String], threshold: f64) -> Vec<Vec<usize>> {
    let mut parent: Vec<_> = (0..prompts.len()).collect();
    let normalized: Vec<_> = prompts.iter().map(|prompt| normalize(prompt)).collect();
    for i in 0..prompts.len() {
        for j in i + 1..prompts.len() {
            if normalized[i] == normalized[j] || similarity(&prompts[i], &prompts[j]) >= threshold {
                let left_root = find_root(&mut parent, i);
                let right_root = find_root(&mut parent, j);
                parent[left_root] = right_root;
            }
        }
    }
    let mut root_positions = HashMap::<usize, usize>::new();
    let mut groups: Vec<Vec<usize>> = Vec::new();
    for index in 0..prompts.len() {
        let root = find_root(&mut parent, index);
        let position = *root_positions.entry(root).or_insert_with(|| {
            groups.push(Vec::new());
            groups.len() - 1
        });
        groups[position].push(index);
    }
    groups
}

pub fn find_leakage(candidate: &[String], reference: &[String], threshold: f64) -> Vec<Duplicate> {
    let reference_norms: Vec<_> = reference.iter().map(|prompt| normalize(prompt)).collect();
    let mut found = Vec::new();
    for prompt in candidate {
        let normalized = normalize(prompt);
        for (other, other_normalized) in reference.iter().zip(reference_norms.iter()) {
            if normalized == *other_normalized {
                found.push(Duplicate {
                    left: prompt.clone(),
                    right: other.clone(),
                    kind: "exact".to_owned(),
                    score: 1.0,
                });
                continue;
            }
            let score = similarity(prompt, other);
            if score >= threshold {
                found.push(Duplicate {
                    left: prompt.clone(),
                    right: other.clone(),
                    kind: "near".to_owned(),
                    score: round_half_even(score, 3),
                });
            }
        }
    }
    found
}
