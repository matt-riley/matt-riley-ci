# matt-riley-ci

Reusable GitHub Actions workflows with repository-owned tasks, small language adapters, and separate publishing jobs. Start with Universal CI; use an adapter when its runtime-specific behavior is useful.

This checkout defines the **next major contract (v4)**. Existing v1/v2/v3 tags keep their existing APIs. Replace `REVIEWED_COMMIT_SHA` in examples with the full tested commit SHA from this implementation/release; do not copy a future `@v4` ref before it exists. Read the [migration guide](docs/migration-v4.md) before upgrading.

## Start with repository-owned CI

Define tools and tasks in your own `mise.toml`. The workflow checks out your repository, not this library, so it cannot use this library's tasks or scripts.

```toml
[tools]
node = "24"
pnpm = "12.8.1"

[tasks.install]
run = "pnpm install --frozen-lockfile"

[tasks.lint]
depends = ["install"]
run = "pnpm run lint"

[tasks.test]
depends = ["install"]
run = "pnpm test"

[tasks.build]
depends = ["install"]
run = "pnpm run build"

[tasks.ci]
depends = ["lint", "test", "build"]
```

Keep commands native to your project: these could equally be Cargo, Python, Swift, Java or Make tasks. No package-manager guessing selects your CI commands.

```yaml
name: CI
on:
  pull_request:
  push:
    branches: [main]
  merge_group:
permissions:
  contents: read
concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
jobs:
  ci:
    uses: matt-riley/matt-riley-ci/.github/workflows/ci.yml@REVIEWED_COMMIT_SHA
    with:
      task-jobs: 4
      install-tools: node pnpm
      save-cache: true
```

`ci` is the default task. Enabled phase flags select repository tasks named install/lint/build/test/vet/fmt instead; `task-prefix` prepends a namespace. Shared dependencies run once in a single graph. A missing task is an error. The default `task-jobs: 1` avoids unexpected concurrent phases; choose parallelism after declaring task dependencies. Cancellation belongs to the caller; the library's independent CI jobs never share a concurrency lock.

For a monorepo, set `working-directory: packages/server`. Artifact and diagnostic paths are relative to that directory. Add `cache-paths` and `cache-dependency-path` for ecosystem-specific caches. See [performance guidance](docs/performance.md), especially when Playwright system dependency installation dominates setup time.

## Workflow catalog

| Workflow | Purpose | Runner contract |
| --- | --- | --- |
| `ci.yml` | Execute the consumer's mise task graph; caches and build/failure artifacts | Linux/macOS, Bash and Python 3 |
| `go-ci.yml` | Native build/test/race/vet/gofmt, coverage and diagnostics | Linux/macOS with setup-go and Python 3 |
| `go-lint.yml` | Pinned golangci-lint with actual outcome reporting | Linux/macOS supported by the upstream lint action |
| `go-security.yml` | Pinned govulncheck | Linux/macOS |
| `aube-ci.yml` | Node package CI through pinned Aube, strict scripts/lockfiles | Linux/macOS supported by Aube |
| `docker-ghcr-publish.yml` | Native/multi-platform GHCR image validation or publishing | Linux with Docker; supported platforms listed in reference |
| `cloudflare-pages-deploy.yml` | Deploy an existing same-run site artifact | Linux; Node used only to run Wrangler |
| `go-goreleaser.yml` | Snapshot validation or tagged release, optional tap token | Linux/macOS supported by GoReleaser |
| `homebrew-formula.yml` | Generate, syntax-check and push a tap formula from release assets | Linux with gh, Python and Ruby |
| `nvim-format.yml` | Pinned StyLua | Linux/macOS x64/arm64 |
| `nvim-lint.yml` | Pinned standalone luacheck, no apt setup | Linux x64; use Universal CI for other platforms |
| `nvim-tests.yml` | Exact Neovim release and pinned mini.test | Linux/macOS x64/arm64 |
| `pnpm-lockfile-sync.yml` | Refresh only a same-repository release PR lockfile | Linux with pnpm/Node |
| `release-please.yml` | Release PRs and tagged releases; generic monorepo outputs | Linux with release-please |
| `request-app-deploy.yml` | Request exact source/artifact deployment from matt-riley/infra | Linux; project-specific target |
| `request-infra-deploy.yml` | Request deployment from an explicit generic infra repository | Linux |
| `tailscale-acl.yml` | Validate/apply policy with workload identity federation | Linux supported by Tailscale's action |

Every input, default, secret, output and job permission is listed in the [generated reference](docs/reference.md). [Complete caller examples](docs/examples.md) include setup, permissions and secrets for each workflow. Runner defaults are GitHub-hosted; arbitrary self-hosted labels must supply the stated tools. Windows PowerShell runners are not supported by Bash adapters.

## Permissions, credentials and trust

Callers must grant the permissions requested by their called workflow. A reusable workflow cannot elevate the caller's token. Start with `contents: read`; grant write permissions only to publishing jobs. Checkouts never persist credentials. Publishing steps use explicit secrets or a temporary credential helper. `registry-token` and `dependency-token` in Universal CI are optional read-only credentials exposed to repository tasks as NODE_AUTH_TOKEN and DEPENDENCY_TOKEN; configure registry/private module access in the consumer's install task and keep tokens out of files/artifacts. These secrets are not available on fork PRs.

`task-env` and `build-env` accept literal multiline KEY=VALUE entries. They reject workflow control variables. Custom command inputs are deliberately executable repository-owned code: only trusted caller maintainers should edit them. Do not forward untrusted PR text or manual user strings into command inputs. Plain inputs such as paths, tags and task names are transported as data and validated.

Writers require trusted events: default/production-branch pushes or manual runs for deployments/dispatch, release tags for GoReleaser/Homebrew, and same-repository release PRs for lockfile synchronization. Protect named GitHub environments and restrict who can invoke manual workflows. Caller `environment` on a reusable job is not passed through automatically: use the workflow's environment input, and configure environment secrets in the caller repository. Environment secrets used by a called job can override same-named passed secrets.

Source/artifact dispatch is only a request. The receiving repository must authenticate the sender, allowlist app/source repositories, verify SHA/ref provenance, retrieve the declared run artifact, compare the SHA-256 digest, and enforce production policy before executing/deploying anything. Never trust a repository_dispatch payload alone as authorization.

### Tailscale ACL

Configure a Tailscale federated identity with the exact repository/workflow and allowed subject/branch claims shown by your GitHub issuer. Grant `id-token: write` to the caller. New GitHub immutable repository/owner IDs can change subject formats; use the actual claims from your issuer rather than copying a repo-name-only example. The default validates PRs and applies default-branch pushes. Explicit `action: apply` also requires a trusted default-branch push/manual run. No long-lived secret is required. Protect the environment for apply and use Tailscale-side identity restrictions; the local guard is only one layer.

## Versioning and maintenance

Pin callers to a reviewed full commit SHA for reproducible runs. A floating major tag accepts compatible fixes; major contract changes get a new major version. This branch does not rewrite existing major tags. Tool/action updates use Renovate, pinned defaults and the same contract suite. Consumer overrides intentionally transfer version compatibility responsibility to the caller.

Only the latest major receives routine maintenance; older versions remain usable but receive no guaranteed backports. A breaking input/default/security behavior change requires a migration note and major release. New workflow adapters need a complete caller, a clean consumer fixture and executable negative cases before inclusion. CODEOWNERS assigns ownership to @matt-riley. Report security issues privately to the maintainer; no response SLA is promised for this personal library.

## Validate locally and publish releases

```sh
mise install
mise run setup
mise run ci
```

Setup installs pinned validators in `.venv`; subsequent checks do not reinstall them. The single check command validates .yml/.yaml syntax, duplicate keys, all action/reusable/container pins, shell/expression semantics, security policy, every executable Python contract and generated reference drift. The hosted suite additionally runs real Go/Aube/mise/Docker/Neovim consumer workflows and verifies build/coverage artifact handoff. PRs and merge queues run the full suite without path filters. Main pushes call that same suite before release-please; release commits therefore validate the exact source revision before advancing a major tag.

Set branch protection to require the final **checks** job. The repository release workflow uses `RELEASE_TAG_TOKEN` for floating tag updates: a PAT/App token with contents write and **workflows: write** access. That latter scope is not a valid workflow `permissions:` key. An ordinary GITHUB_TOKEN may be rejected when moving refs containing workflow files. Use the default GITHUB_TOKEN for release-please when subsequent automatic release-PR CI is not needed; use an explicit App/PAT token when downstream event-triggered checks must run (GitHub suppresses most workflows caused by GITHUB_TOKEN).

If a release exists but major-tag publication failed, manually run Repository Release Please **on that exact release tag**, with `release-tag` set to it. The full suite revalidates that SHA, and the publisher verifies the remote tag target after a guarded push. A different branch revision cannot bless an untested tag. Concurrent releases are serialized and stale tag updates use force-with-lease. GitHub's ordinary concurrency allows one running and one pending run, so intermediate pending runs may be replaced; do not use it as a lossless queue.

The monthly documentation audit and its gh-aw bootstrap were removed. Documentation contract checks run with regular CI.
