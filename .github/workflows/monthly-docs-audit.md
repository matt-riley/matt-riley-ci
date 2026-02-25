---
description: |
  Runs a monthly documentation audit for this repository and publishes a report
  issue with findings, broken examples, and concrete remediation steps.

on:
  schedule:
    - cron: "0 9 1 * *"
  workflow_dispatch:

permissions:
  contents: read
  issues: read
  pull-requests: read

network: defaults

tools:
  github:
    lockdown: false

safe-outputs:
  create-issue:
    title-prefix: "[docs-audit] "
    labels: [documentation, report]
---

# Monthly Documentation Audit

Run a full documentation audit focused on correctness and freshness.

## Scope

- `README.md`
- Reusable workflow files in `.github/workflows/*.yml`
- Documentation-relevant fixtures in `fixtures/**` when referenced by README examples

## Required checks

1. Extract all documented workflow usage snippets from `README.md`.
2. Verify documented inputs, defaults, outputs, and examples match the real workflow contracts in `.github/workflows/*.yml`.
3. Flag stale or inaccurate guidance (missing inputs, renamed fields, outdated defaults, or contradictory behavior notes).
4. Verify referenced files/paths still exist.
5. Prioritize findings by severity:
   - **High**: incorrect usage that can break consumer workflows.
   - **Medium**: ambiguous or incomplete docs likely to confuse users.
   - **Low**: clarity and style improvements.

## Output format

Create one GitHub issue with:

- A short executive summary.
- A findings table with: severity, file/section, problem, suggested fix.
- A "No changes required" statement when everything is accurate.
- A final checklist maintainers can use to update docs quickly.

If there are no findings, still create the issue and explicitly state that docs are up to date for this audit cycle.
