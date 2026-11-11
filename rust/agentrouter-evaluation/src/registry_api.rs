//! Rust-side dataset registry facade mirrored from
//! `agentrouter.evaluation.registry`.

use crate::{adapter_descriptor, profile_datasets, AdapterDescriptor, ADAPTERS, DATASET_NAMES};

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
