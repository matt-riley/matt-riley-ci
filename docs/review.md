# Workflow review and implementation assessment

Reviewed against `5ba0a5d`, with changes staged for the next major API in PR #116. This is a reusable workflow library: its public contract matters as much as whether its own sample repository passes.

## What was good

The existing library already separated common CI, language adapters and publishing workflows; typed reusable inputs made it discoverable. Many action references used full commit SHAs, Renovate provided an update path, Go caches distinguished modules from build outputs, and trusted-branch cache writing was already present in Universal CI. The scoped application dispatcher and Tailscale workload identity were useful foundations. Keeping these strengths was preferable to replacing the library with a new abstraction.

The overall approach remains sensible: a small shared runner contract, repository-owned commands, and specialized adapters where a language or service actually needs one. Language independence should not mean guessing a project's package manager, silently skipping checks, or hiding deployment credentials inside a generic build job.

## Findings and resulting contracts

| Area | Problem or improvement | Implemented approach |
| --- | --- | --- |
| Universal CI | All-disabled phases could pass without checking anything; separate mise invocations repeated task dependencies. | Default repository `ci` task; strict requested names; one graph; configurable parallelism. |
| Tool setup | Broad setup could install irrelevant tools; implicit shim activation can install additional declared tools later. | Optional selected tools; pinned mise; direct installed binary paths; tasks use `--skip-tools`. |
| Monorepos | Working-directory and cache discovery/artifact paths did not consistently describe the same project. | Actual command/setup directory, project-scoped caches and per-line artifact resolution. |
| Caching | Hardcoded stores, incomplete runtime identities, implicit browser caching and competing writers waste work or mix incompatible data. | Runtime-discovered paths, OS/architecture/tool/project/lock identities, optional browser cache and designated trusted writers. |
| Go CI | Library-owned mise tasks were an implicit consumer dependency; quoted overrides and conflicting flags were fragile. | Native Go commands, one toolchain, preserved quoting, strict combinations, coverage and diagnostic artifacts. |
| Go lint/security | Outcome reporting and tool versioning needed clearer contracts; repeated scanner compilation adds setup time. | Pinned defaults, actual outcomes, shared scoped Go caches and exact-version scanner binary cache. |
| Aube | Enabled scripts could be skipped, defaults floated, lockfile checks could miss untracked files. | Pinned Aube, separately installed Node, required scripts and tracked/clean lockfiles, validated build environment. |
| Docker | Validation authenticated unnecessarily; dual architectures/emulation and common cache namespaces increased cost; tagging needed prerelease handling. | Separate read/publish jobs, native default, conditional QEMU, per-image cache/publication lock, stable-only latest tag, attestations and exporter/digest contracts. |
| Pages | Deployment coupled build/package installation with an unsupported authentication claim. | Same-run artifact deployment, supported API token, pinned Wrangler, trusted source and protected environment inputs. |
| GoReleaser | Publication and validation needed explicit separation; missing tap auth could obscure intent. | Nonpublishing snapshot mode; trusted tag publication; explicit App identity and configurable missing-token behavior. |
| Homebrew | Unescaped Ruby values, compulsory platform assets and an assumed CLI test argument made generation brittle. Nested binaries also need their installed basename in the test. | Escaped literal strings, syntax checks, optional platforms, configurable arguments, transient push credential and serialized tap changes. [Homebrew's install implementation](https://docs.brew.sh/rubydoc/Pathname.html#install-instance_method) confirms the basename behavior. |
| Neovim | A requested version did not reliably mean that version; mini source could float; runner support was unclear. | Versioned binary assets, explicit architecture support, immutable mini commit, configurable test paths and failure propagation. |
| Lockfile sync | Writing arbitrary PR branches and retaining write credentials around installation increased risk. | Same-repository release PR guard, lockfile-only installation without lifecycle scripts, transient scoped push and unchanged outcome. |
| Dispatch | Generic App identity, payload validation, source authority and observable acceptance needed stronger contracts. | Explicit target-scoped App, trusted branches, validated complete artifact metadata and outputs; preserve convenient scoped dispatcher. |
| Release | A major tag could advance without proving that its exact target passed checks; annotated refs and racing updates needed care. | Shared full-suite gate, exact SHA comparison, serialized guarded tag moves, remote verification and exact-tag repair path. |
| Cross-cutting behavior | Caller-derived CI concurrency could cancel independent jobs; shell interpolation, retained checkout credentials and vague summaries weakened reliability. | Caller-owned CI cancellation, target-specific writer locks, data through environment, read-only checkout, explicit permissions/timeouts and actual outcomes. |
| Validation/docs | Duplicated/fail-open validation and sample-only coverage missed public API defects; path filters could bypass checks. | One failing local/hosted entrypoint, executable negative cases, real consumer adapters/artifact handoff, merge queue support, caller-permission and documentation contract checks. |
| Maintenance | Scheduled agentic audit and bootstrap added operational complexity. | Removed as requested; generated-reference/caller checks run in normal CI. Added ownership, support policy, examples and migration guidance. |

## Performance verdict

Mise itself was not the source of the apt explosion in the supplied mattriley.tools runs. Its repository install task invoked Playwright system/browser setup in both CI and data generation: each installed 181 apt packages and downloaded 125 MB. The observed failures were later Astro/TypeScript compatibility errors. Exact evidence and a corrected task graph are in [performance.md](performance.md). That external repository was not changed.

The library now avoids repeated task dependencies, unnecessary tools/emulation, deployment rebuilds, implicit browser setup and redundant cache writes. The successful hosted consumer run measured mise setup at 3–5 seconds and Neovim installation at two seconds; cold scanner compilation took nineteen seconds. Fixture measurements establish behavior, not an application benchmark. Measure representative cold and warm consumer runs before promising a percentage improvement. OS browser dependencies still need installation or an appropriate runner/container.

## What remains outside this implementation

The checked-in suite verifies Linux x64 consumers and 41 executable contracts, including real mise graphs, Ruby syntax and local Git publication. Hosted checks exercise Go test/lint/security, GoReleaser snapshots, Aube, Node/Bun/language-neutral mise tasks, Docker validation, Neovim tools/tests and artifact handoff.

Production Cloudflare/GHCR/tap/release/dispatch/Tailscale operations are not exercised using live write credentials. Operators must configure environments, App permissions, registry/service access, branch protection and receiving infrastructure policy. The receiver must verify source and artifact provenance; dispatch acceptance does not prove deployment completion. macOS/ARM execution and self-hosted provisioning also need real consumer validation before relying on them.

My assessment: this is a sound small workflow library after these changes, with a clearer standard contract and materially less unnecessary work. It should remain deliberately modest. Add ecosystem-specific caching/adapters only when real consumers justify them; add clean consumer and negative cases alongside each new adapter. Treat these changes as a major upgrade, test a pinned implementation SHA, and do not silently move existing v1/v2/v3 APIs to this contract.
