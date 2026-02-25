# Copilot instructions for `matt-riley-ci`

## Build, test, and lint commands

This repository is a reusable GitHub Actions workflow library; verification is done through workflow validation + fixture contract tests.

- Validate workflow YAML + SHA pinning (same logic as `.github/workflows/validate-workflows.yml`):
  - `python -m pip install --disable-pip-version-check --quiet pyyaml`
  - Run the inline validator from `.github/workflows/validate-workflows.yml` step **"Validate workflow YAML and action pinning"**.
- Go fixture contract checks:
  - `cd fixtures/go && go test ./...`
  - Single test: `cd fixtures/go && go test -run TestSmoke ./...`
  - Vet/format checks used by reusable Go workflow: `cd fixtures/go && go vet ./...` and `test -z "$(cd fixtures/go && gofmt -l .)"`
- Node fixture contract checks:
  - `cd fixtures/node && npm ci && npm test`
- Bun fixture contract checks:
  - `cd fixtures/bun && bun install --no-save && bun test basic.test.ts`
  - Single test: `cd fixtures/bun && bun test basic.test.ts -t "bun fixture smoke test"`
- Agentic workflow compile/validate (for `.md` -> `.lock.yml` workflows):
  - `gh aw compile monthly-docs-audit`
  - `gh aw compile --validate`

## High-level architecture

- `.github/workflows/go-ci.yml`, `go-lint.yml`, `node-ci.yml`, `bun-ci.yml`, `release-please.yml`, and `docker-ghcr-publish.yml` are reusable `workflow_call` contracts that downstream repositories consume via `matt-riley/matt-riley-ci/.github/workflows/<name>.yml@v1`.
- `.github/workflows/contract-tests.yml` is the integration layer for this repo: it executes those reusable workflows against tiny fixtures in `fixtures/go`, `fixtures/node`, and `fixtures/bun` to catch breaking contract changes.
- `.github/workflows/validate-workflows.yml` is the policy gate: it validates workflow YAML structure and enforces SHA-pinned external actions.
- Agentic workflow authoring uses markdown sources + compiled lock files:
  - Source: `.github/workflows/monthly-docs-audit.md`
  - Compiled artifact: `.github/workflows/monthly-docs-audit.lock.yml`
  - Copilot bootstrap for gh-aw is in `.github/workflows/copilot-setup-steps.yml`.

## Key repository conventions

- Pin every external `uses:` action reference to a full 40-char SHA (validation fails otherwise).
- Keep reusable workflow contracts strictly typed: `on.workflow_call.inputs.<name>.type` must be `string`, `number`, or `boolean`.
- Preserve the existing concurrency-group pattern in reusable workflows:
  - `${{ format('{0}:{1}:{2}', github.workflow, github.repository, github.ref) }}`
- Keep job permissions minimal and explicit (`contents: read` unless write scopes are required, e.g., release/docker publish).
- For agentic workflows, edit the `.md` source and recompile the `.lock.yml`; do not hand-edit generated lock artifacts.
- Keep fixture projects minimal smoke tests; they are compatibility checks for workflow behavior, not full application examples.

## MCP servers relevant to this repository

- `github` MCP server: use for PR/issue/workflow-run investigation while editing reusable workflows.
- `github-mcp-server-actions` MCP server: use for listing workflow runs/jobs and fetching logs during CI debugging.
- `agentic-workflows` MCP server (when running in Copilot Cloud contexts): use for gh-aw workflow authoring/debugging flows referenced by `.github/agents/agentic-workflows.agent.md`.
