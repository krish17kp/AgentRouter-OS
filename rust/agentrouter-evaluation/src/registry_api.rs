//! Rust-side dataset registry facade mirrored from
//! `agentrouter.evaluation.registry`.

use std::path::Path;

use crate::{
    adapter_checksum, adapter_descriptor, describe_adapter, load_adapter_dataset,
    load_agentrouter_gold, profile_datasets, sample_adapter_cases, AdapterDescriptor,
    EvaluationCase, EvaluationDatasetMetadata, ADAPTERS, DATASET_NAMES,
};
use serde_json::{json, Map, Value};

#[derive(Debug, Clone)]
pub struct DatasetSpec {
    pub metadata: EvaluationDatasetMetadata,
    pub fixture: Option<&'static str>,
    pub hf_repo: Option<&'static str>,
}

#[derive(Debug, Clone)]
pub struct DatasetCollection {
    pub cases: Vec<EvaluationCase>,
    pub datasets: Value,
}

pub fn dataset_names() -> &'static [&'static str] {
    &DATASET_NAMES
}

pub fn get_adapter(name: &str) -> Result<&'static AdapterDescriptor, String> {
    adapter_descriptor(name)
}

pub fn try_get_adapter(name: &str) -> Option<&'static AdapterDescriptor> {
    get_adapter(name).ok()
}

pub fn available_adapters() -> &'static [AdapterDescriptor] {
    &ADAPTERS
}

pub fn profile(profile: &str) -> Result<&'static [&'static str], String> {
    profile_datasets(profile)
}

pub fn dataset_spec(name: &str) -> Result<DatasetSpec, String> {
    let (version, license, source, description, fixture, hf_repo, requires_docker, languages) =
        match name {
            "agentrouter-gold" => (
                "v1",
                "project-internal (MIT repo)",
                "benchmarks/classifier_gold_v1.yaml",
                "Human-expectation gold labels for the 7-dimension classifier.",
                None,
                None,
                false,
                vec!["en"],
            ),
            "clinc150" => (
                "plus",
                "CC BY 3.0",
                "https://huggingface.co/datasets/clinc_oos",
                "Intent classification with an explicit out-of-scope class; intents mapped to acceptable AgentRouter task families.",
                Some("clinc150_sample.jsonl"),
                Some("clinc_oos"),
                false,
                vec!["en"],
            ),
            "banking77" => (
                "v1",
                "MIT",
                "https://huggingface.co/datasets/PolyAI/banking77",
                "Fine-grained banking intent queries used to check financial language handling and action-based risk calibration.",
                Some("banking77_sample.jsonl"),
                Some("PolyAI/banking77"),
                false,
                vec!["en"],
            ),
            "massive" => (
                "1.1",
                "CC BY 4.0",
                "https://huggingface.co/datasets/AmazonScience/massive",
                "Multilingual (51-language) intent classification; the smoke fixture covers en/hi/fr for per-language reporting.",
                Some("massive_sample.jsonl"),
                Some("AmazonScience/massive"),
                false,
                vec!["en", "hi", "fr"],
            ),
            "longbench-v2" => (
                "v2",
                "LongBench v2 (see dataset card)",
                "https://huggingface.co/datasets/THUDM/LongBench-v2",
                "Long-context understanding across realistic length buckets. AgentRouter grades inferred context-band and routing.",
                Some("longbench_v2_sample.jsonl"),
                Some("THUDM/LongBench-v2"),
                false,
                vec!["en"],
            ),
            "swebench" => (
                "lite",
                "SWE-bench (MIT code; per-repo licenses apply)",
                "https://www.swebench.com",
                "Real-world GitHub issue resolution. AgentRouter grades inferred classification/routing from issue text, not actual issue-solving (that is the Docker harness full run).",
                Some("swebench_sample.jsonl"),
                Some("princeton-nlp/SWE-bench_Lite"),
                true,
                vec!["en"],
            ),
            "llmrouterbench" => (
                "v1",
                "see benchmark repo",
                "LLMRouterBench",
                "Routing quality with cost/quality tradeoffs. Each case carries per-model quality/cost outcomes; grading needs a caller-supplied model-mapping file (no commercial names in routing logic).",
                Some("llmrouterbench_sample.jsonl"),
                None,
                false,
                vec!["en"],
            ),
            "twinrouterbench" => (
                "v1",
                "see benchmark repo",
                "TwinRouterBench",
                "Multi-agent workflow routing. Static track graded from fixture; dynamic track replays workflows in Docker (full run only).",
                Some("twinrouterbench_sample.jsonl"),
                None,
                true,
                vec!["en"],
            ),
            _ => {
                return Err(adapter_descriptor(name).unwrap_err());
            }
        };
    Ok(DatasetSpec {
        metadata: EvaluationDatasetMetadata {
            name: name.to_owned(),
            version: version.to_owned(),
            license: license.to_owned(),
            source: source.to_owned(),
            description: description.to_owned(),
            requires_network: name != "agentrouter-gold",
            requires_docker,
            languages: languages.into_iter().map(str::to_owned).collect(),
        },
        fixture,
        hf_repo,
    })
}

/// Load and deterministically sample registered offline fixtures in Python
/// profile order. Real mode reports the explicit external-data blocker and
/// never substitutes fixture cases.
pub fn collect(
    names: &[&str],
    project_root: &Path,
    limit: Option<i64>,
    seed: i64,
    source: &str,
    massive_languages: Option<&[String]>,
) -> Result<DatasetCollection, String> {
    let mut cases = Vec::new();
    let mut per_dataset = Map::new();
    for name in names {
        let spec = dataset_spec(name)?;
        let (full_cases, description, status) = if *name == "agentrouter-gold" {
            let path = project_root
                .join("agentrouter")
                .join(spec.metadata.source.as_str());
            let describe = crate::agentrouter_gold_describe(&path);
            let status = describe["availability"]
                .as_str()
                .unwrap_or("skipped_external")
                .to_owned();
            if source == "real" {
                let blocker = "agentrouter-gold: agentrouter-gold: no real loader configured (source unverified)";
                let mut record = json!({"status": "SKIPPED_EXTERNAL", "n": 0, "blocker": blocker});
                if let Some(fields) = describe.as_object() {
                    for (key, value) in fields {
                        record[key] = value.clone();
                    }
                }
                per_dataset.insert((*name).to_owned(), record);
                continue;
            }
            let gold_cases = load_agentrouter_gold(&path)?;
            (gold_cases, describe, status)
        } else {
            let fixture = project_root.join("agentrouter/evaluation/fixtures").join(
                spec.fixture
                    .ok_or_else(|| format!("{name}: fixture path is missing"))?,
            );
            let mut description = describe_adapter(&fixture, &spec.metadata, spec.hf_repo);
            if *name == "llmrouterbench" {
                description["model_mapping_required"] = json!(true);
                description["model_mapping_note"] = json!(
                    "Provide a model-mapping file translating LLMRouterBench model keys to registry entries; commercial names never appear in routing logic."
                );
            }
            let status = description["availability"]
                .as_str()
                .unwrap_or("skipped_external")
                .to_owned();
            let loaded = load_adapter_dataset(&fixture, &spec.metadata, spec.hf_repo, source);
            match loaded {
                Ok(loaded) => (loaded, description, status),
                Err(blocker) if source == "real" => {
                    if *name == "massive" && massive_languages.is_some() {
                        per_dataset.insert(
                            (*name).to_owned(),
                            json!({"status": "SKIPPED_EXTERNAL", "n": 0, "blocker": blocker}),
                        );
                    } else {
                        let mut record =
                            json!({"status": "SKIPPED_EXTERNAL", "n": 0, "blocker": blocker});
                        if let Some(fields) = description.as_object() {
                            for (key, value) in fields {
                                record[key] = value.clone();
                            }
                        }
                        per_dataset.insert((*name).to_owned(), record);
                    }
                    continue;
                }
                Err(error) => return Err(error),
            }
        };
        let selected = if *name == "massive" {
            if let Some(languages) = massive_languages {
                let filtered = full_cases
                    .iter()
                    .filter(|case| languages.contains(&case.language))
                    .cloned()
                    .collect::<Vec<_>>();
                sample_adapter_cases(&filtered, limit, seed)
            } else {
                sample_adapter_cases(&full_cases, limit, seed)
            }
        } else {
            sample_adapter_cases(&full_cases, limit, seed)
        };
        if *name == "massive" && massive_languages.is_some() {
            per_dataset.insert(
                (*name).to_owned(),
                json!({"status": status, "n": selected.len()}),
            );
        } else {
            let mut record = json!({
                "status": if source == "real" { format!("real:{name}") } else { status },
                "n": selected.len(),
                "checksum": adapter_checksum(&full_cases),
            });
            if let Some(fields) = description.as_object() {
                for (key, value) in fields {
                    record[key] = value.clone();
                }
            }
            per_dataset.insert((*name).to_owned(), record);
        }
        cases.extend(selected);
    }
    Ok(DatasetCollection {
        cases,
        datasets: Value::Object(per_dataset),
    })
}
