use agentrouter_evaluation::registry_api::{
    available_adapters, dataset_names, get_adapter, profile, try_get_adapter,
};
use serde_json::json;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let profiles = ["fast", "pr", "nightly", "release", "full"]
        .into_iter()
        .map(|name| Ok((name.to_owned(), json!(profile(name)?))))
        .collect::<Result<serde_json::Map<_, _>, String>>()?;
    let descriptors = dataset_names()
        .iter()
        .map(|name| {
            let descriptor = get_adapter(name).expect("registered dataset has descriptor");
            json!({
                "name": name,
                "module": descriptor.module,
                "class": descriptor.class,
                "available": try_get_adapter(name).is_some(),
            })
        })
        .collect::<Vec<_>>();
    let output = json!({
        "names": dataset_names(),
        "profiles": profiles,
        "adapters": descriptors,
        "unknown_is_none": try_get_adapter("not-a-dataset").is_none(),
        "unknown_error": get_adapter("not-a-dataset").unwrap_err(),
        "available_count": available_adapters().len(),
    });
    println!("{}", serde_json::to_string(&output)?);
    Ok(())
}
