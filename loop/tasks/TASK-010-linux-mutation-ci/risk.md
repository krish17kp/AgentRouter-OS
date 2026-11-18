# TASK-010 risk review

The primary integrity risk is a false green caused by a mutmut crash, partial cache,
unselected execution function, or survivor hidden in aggregate output. The wrapper
uses fresh-checkout semantics, exact version verification, fixed selection patterns,
metadata parsing, completeness gates, distinct exit codes, and an empty-by-default
review allowlist. The workflow runs only for relevant pull-request paths, release
branches, or manual dispatch, avoiding an unbounded whole-repository campaign on
ordinary commits. No secrets, deployments, paid services, or mutable external state
are involved.
