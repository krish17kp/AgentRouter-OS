//! Rust-side dataset registry facade mirrored from
//! `agentrouter.evaluation.registry`.

use std::path::{Path, PathBuf};

use crate::{
    adapter_availability, adapter_checksum, adapter_descriptor, adapter_real_availability,
    describe_adapter, load_adapter_dataset, load_adapter_dataset_with_languages,
    load_agentrouter_gold, profile_datasets, sample_adapter_cases, validate_adapter_cases,
    AdapterDescriptor, EvaluationCase, EvaluationDatasetMetadata, ADAPTERS, DATASET_NAMES,
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

/// Concrete adapter facade matching the shared Python `DatasetAdapter`
/// contract.  The descriptor-only registry remains available for cheap
/// discovery; this facade supplies the metadata and lifecycle methods that a
/// caller needs once it has selected an adapter.
#[derive(Debug, Clone)]
pub struct DatasetAdapter {
    descriptor: &'static AdapterDescriptor,
    spec: DatasetSpec,
}

pub type AdapterFactory = Box<dyn Fn() -> Result<DatasetAdapter, String> + Send + Sync>;

impl DatasetAdapter {
    pub fn name(&self) -> &'static str {
        self.descriptor.name
    }

    pub fn descriptor(&self) -> &'static AdapterDescriptor {
        self.descriptor
    }

    pub fn metadata(&self) -> &EvaluationDatasetMetadata {
        &self.spec.metadata
    }

    fn path(&self, project_root: &Path) -> PathBuf {
        if self.name() == "agentrouter-gold" {
            project_root
                .join("agentrouter")
                .join(&self.spec.metadata.source)
        } else {
            project_root
                .join("agentrouter/evaluation/fixtures")
                .join(self.spec.fixture.expect("registered adapter has fixture"))
        }
    }

    pub fn availability(&self, project_root: &Path) -> &'static str {
        if self.name() == "agentrouter-gold" {
            return crate::agentrouter_gold_availability(&self.path(project_root));
        }
        adapter_availability(&self.path(project_root))
    }

    pub fn real_availability(&self) -> (bool, String) {
        adapter_real_availability(self.name(), self.spec.hf_repo)
    }

    pub fn load(&self, project_root: &Path, source: &str) -> Result<Vec<EvaluationCase>, String> {
        if self.name() == "agentrouter-gold" {
            return match source {
                "fixture" => load_agentrouter_gold(&self.path(project_root)),
                "real" => Err(format!(
                    "{}: no real loader configured (source unverified)",
                    self.name()
                )),
                _ => Err(format!("{}: unknown source '{source}'", self.name())),
            };
        }
        load_adapter_dataset(
            &self.path(project_root),
            &self.spec.metadata,
            self.spec.hf_repo,
            source,
        )
    }

    pub fn prepare(&self, project_root: &Path, limit: Option<i64>) -> Result<Value, String> {
        let cases = self.load(project_root, "real")?;
        let cases = sample_adapter_cases(&cases, limit, 0);
        Ok(json!({
            "dataset": self.metadata().name,
            "source": self.metadata().source,
            "hf_repo": self.spec.hf_repo,
            "revision": Value::Null,
            "license": self.metadata().license,
            "downloaded_records": cases.len(),
            "status": "REAL",
        }))
    }

    pub fn sample(
        &self,
        project_root: &Path,
        limit: Option<i64>,
        seed: i64,
        source: &str,
    ) -> Result<Vec<EvaluationCase>, String> {
        Ok(sample_adapter_cases(
            &self.load(project_root, source)?,
            limit,
            seed,
        ))
    }

    pub fn validate(&self, cases: &[EvaluationCase]) -> Result<(), String> {
        validate_adapter_cases(&self.spec.metadata, cases)
    }

    pub fn checksum(&self, project_root: &Path, source: &str) -> Result<String, String> {
        Ok(adapter_checksum(&self.load(project_root, source)?))
    }

    pub fn describe(&self, project_root: &Path) -> Value {
        if self.name() == "agentrouter-gold" {
            return crate::agentrouter_gold_describe(&self.path(project_root));
        }
        describe_adapter(
            &self.path(project_root),
            &self.spec.metadata,
            self.spec.hf_repo,
        )
    }
}

pub fn dataset_names() -> &'static [&'static str] {
    &DATASET_NAMES
}

pub fn get_adapter(name: &str) -> Result<&'static AdapterDescriptor, String> {
    adapter_descriptor(name)
}

pub fn adapter(name: &str) -> Result<DatasetAdapter, String> {
    let descriptor = get_adapter(name)?;
    Ok(DatasetAdapter {
        descriptor,
        spec: dataset_spec(name)?,
    })
}

pub fn try_adapter(name: &str) -> Option<DatasetAdapter> {
    adapter(name).ok()
}

/// Return lazy, callable factories matching Python's `available_adapters`.
/// Factories keep construction separate from cheap registry discovery.
pub fn available_adapter_factories() -> Vec<(&'static str, AdapterFactory)> {
    ADAPTERS
        .iter()
        .map(|descriptor| {
            let name = descriptor.name;
            (name, Box::new(move || adapter(name)) as AdapterFactory)
        })
        .collect()
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
    // Python treats an explicitly empty MASSIVE language list as no filter.
    let massive_languages = massive_languages.filter(|languages| !languages.is_empty());
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
            let loaded = if *name == "massive" && source == "real" {
                load_adapter_dataset_with_languages(
                    &fixture,
                    &spec.metadata,
                    spec.hf_repo,
                    source,
                    massive_languages,
                )
            } else {
                load_adapter_dataset(&fixture, &spec.metadata, spec.hf_repo, source)
            };
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

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    #[test]
    fn adapter_facade_exposes_shared_contract_for_fixture() {
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..");
        let adapter = adapter("clinc150").expect("registered adapter");
        assert_eq!(adapter.name(), "clinc150");
        assert_eq!(adapter.metadata().name, "clinc150");
        assert_eq!(adapter.availability(&root), "fixture_only");

        let cases = adapter.load(&root, "fixture").expect("fixture should load");
        assert!(!cases.is_empty());
        adapter.validate(&cases).expect("fixture validates");
        assert_eq!(adapter.checksum(&root, "fixture").unwrap().len(), 16);
        assert_eq!(
            adapter.sample(&root, Some(2), 7, "fixture").unwrap().len(),
            2
        );
        assert_eq!(adapter.describe(&root)["name"], "clinc150");
    }

    #[test]
    fn adapter_facade_keeps_real_mode_explicitly_external() {
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..");
        let adapter = adapter("banking77").expect("registered adapter");
        let (available, reason) = adapter.real_availability();
        assert!(!available);
        assert!(reason.contains("datasets") || reason.contains("real loader"));
        let error = adapter.load(&root, "real").unwrap_err();
        assert!(error.contains("banking77:"));
    }

    #[test]
    fn gold_adapter_reports_ready_when_the_committed_benchmark_exists() {
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..");
        let adapter = adapter("agentrouter-gold").expect("registered gold adapter");
        assert_eq!(adapter.availability(&root), "ready");
        let cases = adapter.load(&root, "fixture").expect("gold fixture loads");
        assert_eq!(cases.len(), 165);
        assert_eq!(adapter.describe(&root)["availability"], "ready");
    }

    #[test]
    fn available_factories_construct_each_registered_adapter_lazily() {
        let factories = available_adapter_factories();
        assert_eq!(factories.len(), DATASET_NAMES.len());
        for (name, factory) in factories {
            let instance = factory().expect("registered factory constructs");
            assert_eq!(instance.name(), name);
        }
    }
}
