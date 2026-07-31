# Codex capability decisions

The complete per-capability decision is machine-readable in
`loop/PLUGIN_SKILL_INVENTORY.yaml`. The smallest effective set for this takeover is:

- local shell plus `apply_patch` for repository work;
- web access only for primary mutmut and GitHub Actions documentation;
- collaboration agents only for the independent TASK-008/TASK-009 reviews the owner
  explicitly required;
- the GitHub integration/CLI only after the release branch is ready to push and inspect.

No visual, office, calendar, messaging, deployment, Supabase, Figma, Canva, or
skill/plugin-creation capability is relevant. None is installed or invoked. The
recommended but uninstalled enterprise connectors remain uninstalled because this task
does not need their data and granting access would expand privilege without benefit.

The inherited `.claude` agents, skills, and hooks are preserved as project assets. They
do not enforce Codex behavior. Their durable safety rules now live in root `AGENTS.md`,
repository tests, the mutation wrapper, and GitHub workflows.
