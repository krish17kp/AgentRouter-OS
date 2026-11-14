//! Human-operated context-band annotation workflow mirrored from
//! `agentrouter.annotation.cli`.
//!
//! This module only prepares blinded candidate packs and records human input.
//! It never predicts or invents annotation labels.

use std::collections::BTreeMap;
use std::io::{self, BufRead, Write};
use std::path::{Path, PathBuf};

use agentrouter_core::ContextBand;
use chrono::{SecondsFormat, Utc};
use serde_json::{json, Value};

use crate::annotation_schema::{
    AdjudicatedItem, AnnotatorLabel, Candidate, DatasetManifest, ItemLabels, CATEGORIES, SPLITS,
};
use crate::{AnnotationAdjudication, AnnotationInputItem};

fn project_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
}

fn parse_value(args: &mut impl Iterator<Item = String>, flag: &str) -> Result<String, String> {
    let value = args.next().ok_or_else(|| format!("{flag} needs a value"))?;
    if value.starts_with('-') {
        return Err(format!("{flag} needs a value"));
    }
    Ok(value)
}

fn parse_signed_value(
    args: &mut impl Iterator<Item = String>,
    flag: &str,
) -> Result<String, String> {
    args.next().ok_or_else(|| format!("{flag} needs a value"))
}

fn read_candidates(path: &Path) -> Result<Vec<Candidate>, String> {
    crate::annotation_store::load_candidates(path)
}

fn read_labels(path: &Path) -> Result<Vec<ItemLabels>, String> {
    crate::annotation_store::load_labels(path)
}

fn read_frozen_prompts(root: &Path) -> Vec<String> {
    let path = root.join("agentrouter/benchmarks/context_band_holdout_v1.yaml");
    let Ok(text) = std::fs::read_to_string(path) else {
        return Vec::new();
    };
    let Ok(value) = serde_yaml::from_str::<Value>(&text) else {
        return Vec::new();
    };
    value["cases"]
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(|case| case["prompt"].as_str().map(str::to_owned))
        .collect()
}

fn candidate_id_set(labels: &[ItemLabels]) -> std::collections::BTreeSet<String> {
    crate::annotation_packs::labelled_ids(labels)
}

fn gen_candidates(args: impl Iterator<Item = String>) -> Result<i32, String> {
    let mut out = None;
    let mut count = 120_i64;
    let mut seed = "20260731".to_owned();
    let mut args = args;
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--out" => out = Some(PathBuf::from(parse_value(&mut args, "--out")?)),
            "--count" => {
                count = parse_value(&mut args, "--count")?
                    .parse()
                    .map_err(|_| "invalid --count value".to_owned())?;
                if count < CATEGORIES.len() as i64 {
                    return Err(format!("--count must be at least {}", CATEGORIES.len()));
                }
            }
            "--seed" => seed = parse_signed_value(&mut args, "--seed")?,
            flag => return Err(format!("unknown option '{flag}'")),
        }
    }
    let out = out.ok_or_else(|| "--out is required".to_owned())?;
    let pool = crate::annotation_candidates::generate(Some(count), &seed)?;
    crate::annotation_store::save_candidates(&out, &pool)?;
    println!(
        "Wrote {} candidates to {} (unlabelled; humans assign bands).",
        pool.len(),
        out.display()
    );
    Ok(0)
}

fn pack(args: impl Iterator<Item = String>) -> Result<i32, String> {
    let root = project_root();
    let mut annotator = None;
    let mut seed = None;
    let mut candidates = root.join("agentrouter/benchmarks/context_band/candidates_v1.yaml");
    let mut out = None;
    let mut args = args;
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--annotator" => annotator = Some(parse_value(&mut args, "--annotator")?),
            "--seed" => seed = Some(parse_signed_value(&mut args, "--seed")?),
            "--candidates" => candidates = PathBuf::from(parse_value(&mut args, "--candidates")?),
            "--out" => out = Some(PathBuf::from(parse_value(&mut args, "--out")?)),
            flag => return Err(format!("unknown option '{flag}'")),
        }
    }
    let annotator = annotator.ok_or_else(|| "--annotator is required".to_owned())?;
    let seed = seed.ok_or_else(|| "--seed is required".to_owned())?;
    let out = out.ok_or_else(|| "--out is required".to_owned())?;
    let candidates = read_candidates(&candidates)?;
    let ordered = crate::annotation_packs::build_pack(&candidates, &seed)?;
    crate::annotation_store::save_candidates(&out, &ordered)?;
    println!(
        "Wrote blinded pack of {} candidates for '{}' -> {}.",
        ordered.len(),
        annotator,
        out.display()
    );
    Ok(0)
}

fn prompt_line<R: BufRead, W: Write>(
    reader: &mut R,
    writer: &mut W,
    prompt: &str,
) -> io::Result<Option<String>> {
    write!(writer, "{prompt}: ")?;
    writer.flush()?;
    let mut value = String::new();
    if reader.read_line(&mut value)? == 0 {
        return Ok(None);
    }
    Ok(Some(value.trim().to_owned()))
}

fn annotate(args: impl Iterator<Item = String>) -> Result<i32, String> {
    let mut args = args;
    let pack_path = args
        .next()
        .ok_or_else(|| "annotate needs a blinded pack path".to_owned())?;
    let mut annotator = None;
    let mut out = None;
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--annotator" => annotator = Some(parse_value(&mut args, "--annotator")?),
            "--out" => out = Some(PathBuf::from(parse_value(&mut args, "--out")?)),
            flag => return Err(format!("unknown option '{flag}'")),
        }
    }
    let annotator = annotator.ok_or_else(|| "--annotator is required".to_owned())?;
    let out = out.ok_or_else(|| "--out is required".to_owned())?;
    let pool = read_candidates(Path::new(&pack_path))?;
    let mut items = if out.exists() {
        read_labels(&out)?
    } else {
        Vec::new()
    };
    let done = candidate_id_set(&items);
    let todo = pool
        .iter()
        .filter(|candidate| !done.contains(&candidate.id))
        .cloned()
        .collect::<Vec<_>>();
    println!(
        "Annotating {} of {} candidates as '{}' ({} already done). EOF to pause.",
        todo.len(),
        pool.len(),
        annotator,
        items.len()
    );
    let stdin = io::stdin();
    let stdout = io::stdout();
    let mut reader = stdin.lock();
    let mut writer = stdout.lock();
    for candidate in todo {
        println!("\n[{}] {}", candidate.category, candidate.prompt);
        let Some(choice) = prompt_line(&mut reader, &mut writer, "band (s/m/l/a=abstain)")
            .map_err(|error| error.to_string())?
        else {
            println!(
                "\nPaused. {} labelled so far; saved to {}.",
                items.len(),
                out.display()
            );
            return Ok(0);
        };
        let choice = choice.to_ascii_lowercase();
        let abstain = choice.starts_with('a');
        let band = if abstain {
            None
        } else {
            match choice.as_str() {
                "s" => Some(ContextBand::Small),
                "m" => Some(ContextBand::Medium),
                "l" => Some(ContextBand::Large),
                _ => {
                    println!("skipped (invalid band)");
                    continue;
                }
            }
        };
        let Some(rationale) = prompt_line(&mut reader, &mut writer, "rationale")
            .map_err(|error| error.to_string())?
        else {
            println!(
                "\nPaused. {} labelled so far; saved to {}.",
                items.len(),
                out.display()
            );
            return Ok(0);
        };
        let Some(confidence_text) = prompt_line(&mut reader, &mut writer, "confidence 0-1 [0.7]")
            .map_err(|error| error.to_string())?
        else {
            println!(
                "\nPaused. {} labelled so far; saved to {}.",
                items.len(),
                out.display()
            );
            return Ok(0);
        };
        let confidence = if confidence_text.is_empty() {
            0.7
        } else {
            confidence_text
                .parse::<f64>()
                .map_err(|_| "confidence must be a number between 0 and 1".to_owned())?
        };
        if !(0.0..=1.0).contains(&confidence) {
            return Err("confidence must be between 0 and 1".to_owned());
        }
        let label = AnnotatorLabel {
            annotator: annotator.clone(),
            band,
            abstain,
            rationale: if rationale.is_empty() {
                "n/a".to_owned()
            } else {
                rationale
            },
            confidence,
            at: Some(Utc::now().to_rfc3339_opts(SecondsFormat::Micros, false)),
        };
        label.validate()?;
        items.push(ItemLabels {
            candidate_id: candidate.id,
            prompt: candidate.prompt,
            category: candidate.category,
            labels: vec![label],
        });
        crate::annotation_store::save_labels(&out, &items)?;
    }
    println!("Wrote {} labels to {}.", items.len(), out.display());
    Ok(0)
}

fn progress(args: impl Iterator<Item = String>) -> Result<i32, String> {
    let mut args = args;
    let pack_path = args
        .next()
        .ok_or_else(|| "progress needs an annotator pack path".to_owned())?;
    let mut labels_path = None;
    while let Some(arg) = args.next() {
        if arg == "--labels" {
            labels_path = Some(PathBuf::from(parse_value(&mut args, "--labels")?));
        } else {
            return Err(format!("unknown option '{arg}'"));
        }
    }
    let labels_path = labels_path.ok_or_else(|| "--labels is required".to_owned())?;
    let pool = read_candidates(Path::new(&pack_path))?;
    let labels = if labels_path.exists() {
        read_labels(&labels_path)?
    } else {
        Vec::new()
    };
    let (total, done, remaining) = crate::annotation_packs::progress(&pool, &labels);
    println!("{done}/{total} labelled, {remaining} remaining.");
    Ok(0)
}

fn export(args: impl Iterator<Item = String>) -> Result<i32, String> {
    let mut args = args;
    let labels_path = args
        .next()
        .ok_or_else(|| "export needs a labels JSONL path".to_owned())?;
    let mut csv_path = None;
    while let Some(arg) = args.next() {
        if arg == "--csv" {
            csv_path = Some(PathBuf::from(parse_value(&mut args, "--csv")?));
        } else {
            return Err(format!("unknown option '{arg}'"));
        }
    }
    let csv_path = csv_path.ok_or_else(|| "--csv is required".to_owned())?;
    let labels = read_labels(Path::new(&labels_path))?;
    if let Some(parent) = csv_path.parent() {
        std::fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    }
    std::fs::write(&csv_path, crate::annotation_packs::labels_to_csv(&labels))
        .map_err(|error| error.to_string())?;
    println!(
        "Exported {} labelled items to {}.",
        labels.len(),
        csv_path.display()
    );
    Ok(0)
}

fn adjudication_pack(args: impl Iterator<Item = String>) -> Result<i32, String> {
    let mut args = args;
    let mut labels = Vec::new();
    let mut out = None;
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--labels" => labels.push(PathBuf::from(parse_value(&mut args, "--labels")?)),
            "--out" => out = Some(PathBuf::from(parse_value(&mut args, "--out")?)),
            flag => return Err(format!("unknown option '{flag}'")),
        }
    }
    if labels.is_empty() {
        return Err("at least one --labels path is required".to_owned());
    }
    let out = out.ok_or_else(|| "--out is required".to_owned())?;
    let label_sets = labels
        .iter()
        .map(|path| read_labels(path))
        .collect::<Result<Vec<_>, _>>()?;
    let disputed = crate::annotation_packs::adjudication_candidates(&label_sets);
    crate::annotation_store::save_candidates(&out, &disputed)?;
    println!(
        "Wrote {} disagreed item(s) to {} (no auto-adjudication).",
        disputed.len(),
        out.display()
    );
    Ok(0)
}

fn count_values<'a>(values: impl Iterator<Item = &'a str>) -> BTreeMap<String, serde_json::Number> {
    let mut raw_counts = BTreeMap::<String, u64>::new();
    for value in values {
        *raw_counts.entry(value.to_owned()).or_default() += 1;
    }
    raw_counts
        .into_iter()
        .map(|(name, count)| (name, serde_json::Number::from(count)))
        .collect()
}

fn build(args: impl Iterator<Item = String>) -> Result<i32, String> {
    let mut args = args;
    let mut labels_paths = Vec::new();
    let mut out_dir = None;
    let mut version = "v2.0.0".to_owned();
    let mut adjudications_path = None;
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--labels" => labels_paths.push(PathBuf::from(parse_value(&mut args, "--labels")?)),
            "--out-dir" => out_dir = Some(PathBuf::from(parse_value(&mut args, "--out-dir")?)),
            "--version" => version = parse_value(&mut args, "--version")?,
            "--adjudications" => {
                adjudications_path = Some(PathBuf::from(parse_value(&mut args, "--adjudications")?))
            }
            flag => return Err(format!("unknown option '{flag}'")),
        }
    }
    if labels_paths.is_empty() {
        return Err("at least one --labels path is required".to_owned());
    }
    let out_dir = out_dir.ok_or_else(|| "--out-dir is required".to_owned())?;
    let label_sets = labels_paths
        .iter()
        .map(|path| read_labels(path))
        .collect::<Result<Vec<_>, _>>()?;
    let merged = crate::annotation_packs::merge_by_candidate(&label_sets);
    let mut decisions = BTreeMap::<String, AnnotationAdjudication>::new();
    if let Some(path) = adjudications_path.filter(|path| path.exists()) {
        let text = std::fs::read_to_string(path).map_err(|error| error.to_string())?;
        let rows: Vec<Value> = serde_json::from_str(&text).map_err(|error| error.to_string())?;
        for row in rows {
            let id = row["candidate_id"]
                .as_str()
                .ok_or_else(|| "adjudication is missing candidate_id".to_owned())?
                .to_owned();
            let adjudication: AnnotationAdjudication = serde_json::from_value(json!({
                "adjudicator": row["adjudicator"],
                "band": row["band"],
                "abstain": row["abstain"].as_bool().unwrap_or(false),
                "rationale": row["rationale"],
                "confidence": row.get("confidence").cloned().unwrap_or(json!(0.6)),
            }))
            .map_err(|error| error.to_string())?;
            decisions.insert(id, adjudication);
        }
    }

    let mut resolved = Vec::new();
    let mut unresolved = Vec::new();
    for item in &merged {
        let input: AnnotationInputItem =
            serde_json::from_value(serde_json::to_value(item).map_err(|error| error.to_string())?)
                .map_err(|error| error.to_string())?;
        let output = crate::resolve_annotation(
            &input,
            "generated_candidate",
            decisions.get(&item.candidate_id),
        );
        if let Some(output) = output {
            let item: AdjudicatedItem =
                serde_json::from_value(output).map_err(|error| error.to_string())?;
            item.validate()?;
            resolved.push(item);
        } else {
            unresolved.push(item.candidate_id.clone());
        }
    }
    if !unresolved.is_empty() {
        eprintln!(
            "{} disagreed item(s) need adjudication: {}{}",
            unresolved.len(),
            unresolved
                .iter()
                .take(8)
                .cloned()
                .collect::<Vec<_>>()
                .join(", "),
            if unresolved.len() > 8 { "..." } else { "" }
        );
        return Ok(2);
    }

    let root = project_root();
    let frozen = read_frozen_prompts(&root);
    let values = resolved
        .iter()
        .map(serde_json::to_value)
        .collect::<Result<Vec<_>, _>>()
        .map_err(|error| error.to_string())?;
    let split_values = match crate::annotation_splits::partition(&values, &frozen, None) {
        Ok(value) => value,
        Err(error) => {
            eprintln!("Refusing to build: {error}");
            eprintln!("Remove or relabel the leaking item, then rebuild.");
            return Ok(2);
        }
    };
    std::fs::create_dir_all(&out_dir).map_err(|error| error.to_string())?;
    let mut split_counts = BTreeMap::new();
    let mut split_sha = BTreeMap::new();
    let mut all_items = Vec::new();
    let mut split_items = BTreeMap::<String, Vec<AdjudicatedItem>>::new();
    for split in SPLITS {
        let rows = split_values[split]
            .as_array()
            .ok_or_else(|| format!("{split} split is not an array"))?;
        let items = rows
            .iter()
            .cloned()
            .map(serde_json::from_value::<AdjudicatedItem>)
            .collect::<Result<Vec<_>, _>>()
            .map_err(|error| error.to_string())?;
        let path = out_dir.join(format!("context_band_{split}_{version}.yaml"));
        crate::annotation_store::save_dataset(&path, &items)?;
        split_counts.insert(
            split.to_owned(),
            serde_json::Number::from(items.len() as u64),
        );
        split_sha.insert(
            split.to_owned(),
            crate::annotation_store::split_sha256(&items)?,
        );
        all_items.extend(items.iter().cloned());
        split_items.insert(split.to_owned(), items);
    }
    let dev_prompts = split_items["dev"]
        .iter()
        .map(|item| item.prompt.clone())
        .collect::<Vec<_>>();
    let holdout_prompts = split_items["holdout"]
        .iter()
        .map(|item| item.prompt.clone())
        .collect::<Vec<_>>();
    let leakage = json!({
        "frozen_holdout_prompts_checked": frozen.len(),
        "dev_leaks": crate::annotation_dedup::find_leakage(&dev_prompts, &frozen, crate::annotation_dedup::NEAR_THRESHOLD).len(),
        "holdout_leaks": crate::annotation_dedup::find_leakage(&holdout_prompts, &frozen, crate::annotation_dedup::NEAR_THRESHOLD).len(),
    });
    let leak_path = out_dir.join("leakage_report.json");
    std::fs::write(
        &leak_path,
        format!(
            "{}\n",
            serde_json::to_string_pretty(&leakage).map_err(|error| error.to_string())?
        ),
    )
    .map_err(|error| error.to_string())?;
    let categories = count_values(all_items.iter().map(|item| item.category.as_str()));
    let bands = count_values(
        all_items
            .iter()
            .filter(|item| !item.abstained)
            .filter_map(|item| {
                item.band.map(|band| match band {
                    ContextBand::Small => "small",
                    ContextBand::Medium => "medium",
                    ContextBand::Large => "large",
                })
            }),
    );
    let manifest = DatasetManifest {
        schema_version: serde_json::Number::from(1),
        dataset: "agentrouter-context-band-v2".to_owned(),
        version: version.clone(),
        created: Utc::now().date_naive().to_string(),
        split_counts,
        split_sha256: split_sha,
        category_counts: categories,
        band_counts: bands,
        frozen_holdout_untouched: true,
        leakage_report: Some("leakage_report.json".to_owned()),
        provenance: "TASK-011 candidate-generated, human-review-pending; frozen holdout untouched."
            .to_owned(),
    };
    crate::annotation_store::save_manifest(
        &out_dir.join(format!("manifest_{version}.json")),
        &manifest,
    )?;
    println!(
        "Built dataset {version}: {}. Leakage report -> {}.",
        serde_json::to_string(&manifest.split_counts).map_err(|error| error.to_string())?,
        leak_path.display()
    );
    Ok(0)
}

fn compare(args: impl Iterator<Item = String>) -> Result<i32, String> {
    let mut args = args;
    let dev = args
        .next()
        .ok_or_else(|| "compare needs a dev dataset path".to_owned())?;
    let mut out = None;
    let mut threshold = 0.6_f64;
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--out" => out = Some(PathBuf::from(parse_value(&mut args, "--out")?)),
            "--hybrid-threshold" => {
                threshold = parse_value(&mut args, "--hybrid-threshold")?
                    .parse()
                    .map_err(|_| "invalid --hybrid-threshold value".to_owned())?;
                if !(0.0..=1.0).contains(&threshold) {
                    return Err("--hybrid-threshold must be between 0 and 1".to_owned());
                }
            }
            flag => return Err(format!("unknown option '{flag}'")),
        }
    }
    let items = crate::annotation_store::load_dataset(Path::new(&dev))?;
    let reports = crate::annotation_compare::compare_all(&items, threshold)?;
    for strategy in crate::annotation_compare::STRATEGIES {
        let row = &reports[strategy];
        println!(
            "{strategy:7} acc={} macroF1={} recall={} CI={} ECE={} rules_fallback={} abstained={}",
            row["accuracy"],
            row["macro_f1"],
            row["per_band_recall"],
            row["acc_ci95"],
            row["ece"],
            row["rules_fallback_rate"],
            row["abstained_items"]
        );
    }
    if let Some(path) = out {
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent).map_err(|error| error.to_string())?;
        }
        let mut text = serde_json::to_string_pretty(&reports).map_err(|error| error.to_string())?;
        text.push('\n');
        std::fs::write(&path, text).map_err(|error| error.to_string())?;
        println!("Wrote comparison report to {}.", path.display());
    }
    Ok(0)
}

fn leakage(args: impl Iterator<Item = String>) -> Result<i32, String> {
    let mut args = args;
    let path = args
        .next()
        .ok_or_else(|| "leakage needs a dataset path".to_owned())?;
    if args.next().is_some() {
        return Err("leakage accepts one dataset path".to_owned());
    }
    let items = crate::annotation_store::load_dataset(Path::new(&path))?;
    let frozen = read_frozen_prompts(&project_root());
    let prompts = items
        .iter()
        .map(|item| item.prompt.clone())
        .collect::<Vec<_>>();
    let leaks = crate::annotation_dedup::find_leakage(
        &prompts,
        &frozen,
        crate::annotation_dedup::NEAR_THRESHOLD,
    );
    println!(
        "Checked {} items vs {} frozen prompts: {} leak(s).",
        items.len(),
        frozen.len(),
        leaks.len()
    );
    for leak in leaks.iter().take(20) {
        println!(
            "  {} {}: {:?} ~ {:?}",
            leak.kind, leak.score, leak.left, leak.right
        );
    }
    Ok(if leaks.is_empty() { 0 } else { 1 })
}

/// Run a Python-compatible `dataset` subcommand.
pub fn run(args: impl Iterator<Item = String>) -> Result<i32, String> {
    let mut args = args;
    let command = args.next().ok_or_else(|| {
        "usage: agentrouter-evaluate dataset <gen-candidates|pack|annotate|progress|export|adjudication-pack|build|compare|leakage> [options]".to_owned()
    })?;
    if matches!(command.as_str(), "-h" | "--help") {
        println!("usage: agentrouter-evaluate dataset <gen-candidates|pack|annotate|progress|export|adjudication-pack|build|compare|leakage> [options]");
        println!("No annotation command generates labels; only explicit human input is recorded.");
        return Ok(0);
    }
    let remaining = args.collect::<Vec<_>>();
    if remaining
        .iter()
        .any(|arg| matches!(arg.as_str(), "-h" | "--help"))
    {
        let help = match command.as_str() {
            "gen-candidates" => "usage: agentrouter-evaluate dataset gen-candidates --out PATH [--count N] [--seed INTEGER]\nGenerate an unlabelled candidate pool for human review.",
            "pack" => "usage: agentrouter-evaluate dataset pack --annotator ID --seed INTEGER [--candidates PATH] --out PATH\nWrite a blinded, independently ordered pack.",
            "annotate" => "usage: agentrouter-evaluate dataset annotate PACK --annotator ID --out LABELS.jsonl\nCollect explicit human labels; EOF pauses and saves each completed item.",
            "progress" => "usage: agentrouter-evaluate dataset progress PACK --labels LABELS.jsonl\nPrint counts only; label values are never shown.",
            "export" => "usage: agentrouter-evaluate dataset export LABELS.jsonl --csv OUTPUT.csv\nExport the recorded labels to CSV.",
            "adjudication-pack" => "usage: agentrouter-evaluate dataset adjudication-pack --labels LABELS.jsonl [--labels LABELS.jsonl ...] --out PACK.yaml\nWrite a blinded pack containing items requiring human adjudication.",
            "build" => "usage: agentrouter-evaluate dataset build --labels LABELS.jsonl [--labels LABELS.jsonl ...] --out-dir DIR [--version VERSION] [--adjudications JSON]\nResolve reviewed labels, refuse conflicts, and build leakage-checked splits.",
            "compare" => "usage: agentrouter-evaluate dataset compare DEV.yaml [--out REPORT.json] [--hybrid-threshold 0..1]\nCompare rules, learned, and hybrid strategies on the dev split.",
            "leakage" => "usage: agentrouter-evaluate dataset leakage DATASET.yaml\nCheck candidate prompts against frozen holdout prompts only.",
            _ => "usage: agentrouter-evaluate dataset <gen-candidates|pack|annotate|progress|export|adjudication-pack|build|compare|leakage> [options]\nNo annotation command generates labels; only explicit human input is recorded.",
        };
        println!("{help}");
        return Ok(0);
    }
    let args = remaining.into_iter();
    match command.as_str() {
        "gen-candidates" => gen_candidates(args),
        "pack" => pack(args),
        "annotate" => annotate(args),
        "progress" => progress(args),
        "export" => export(args),
        "adjudication-pack" => adjudication_pack(args),
        "build" => build(args),
        "compare" => compare(args),
        "leakage" => leakage(args),
        _ => Err(format!("unknown dataset command '{command}'")),
    }
}
