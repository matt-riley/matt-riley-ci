# Workflow library implementation

Baseline: clean `main` updated from origin to `5ba0a5d`; implementation branch `codex/standard-workflows`.

The user authorized all bugs and improvements from the review, including removal of the monthly documentation audit. No production publishing or deployment is part of verification. Contract changes are documented for the next major release.

## Requirements and evidence

- [x] Universal CI: repository-owned `ci` task by default, strict requested tasks, real working-directory semantics, one task-graph execution, private dependency credentials, artifacts and outcomes.
- [x] All reusable jobs: distinct namespaces or caller-owned concurrency, safe shell data transport, explicit permissions/timeouts and platform contracts; trusted mutation events and environments.
- [x] Go adapters: standalone Go commands, single authoritative toolchain, quoted overrides, strict input validation, module-aware caches, useful coverage/failure artifacts.
- [x] Aube adapter: pinned default, strict scripts/lockfiles including untracked changes, validated environment and consumer tests.
- [x] Docker: credential-free validation, stable/prerelease tag rules, per-image caches, attestation defaults, single build step, configurable output/export and digest.
- [x] Cloudflare: language-neutral artifact deployment, build/auth separation, supported API-token authentication, environment/concurrency controls and deployment outputs.
- [x] Dispatch: explicit least-privilege App identity, trusted source events, validated payload/repository metadata, observable dispatch outputs; preserve new scoped dispatcher.
- [x] Homebrew: escaped Ruby values, syntax validation before push, optional platforms/test command, serialized tap updates, temporary credential helper, explicit skipped/published outcomes.
- [x] Neovim: actual pinned version installation, supported runner/architecture validation, pinned mini source, configurable test paths and failure propagation.
- [x] Lockfile sync: same-repository release PR guard, install without persisted write credentials, scoped pushes and distinct calls.
- [x] Release: coherent token/event guidance, exact tested SHA gate, serialized tag moves, exact target verification and repair path.
- [x] Validation: one fail-closed local/hosted command, YAML and semantic/action security checks, all contract tests, no path-filter blind spots, merge queue support.
- [x] Consumer coverage: clean standalone and nested fixtures; negative cases and artifacts; hosted validation on the implementation revision.
- [x] Documentation: complete minimal callers, prerequisites, permission/ownership/security/platform contracts, input/output reference, next-major migration and support policy, CODEOWNERS.
- [x] Remove monthly audit source/generated workflow and unused gh-aw bootstrap/configuration.
- [x] Performance: execute shared task dependencies once, scope caches to projects/toolchains, install only necessary tools, avoid deploy rebuilds and unnecessary emulation, and measure representative consumer runs.

## Local evidence

Implemented the core/specialized contracts, writer guards, scoped caches, fast binary setup, complete caller/reference/migration/performance documentation, and audit removal. The single local entrypoint passes actionlint with shellcheck, zizmor offline policy, 38 executable contracts, and generated-reference drift checks. Real mise dependency graphs execute shared installation once; real local Git remotes verify annotated major-tag updates, idempotence, exact tested SHA rejection, and rollback rejection. Ruby syntax checks validate generated formulas with quoted/interpolated-looking input.

The user-provided mattriley.tools example showed mise setup succeeding and repository Playwright setup installing 181 apt packages in two jobs. Build failures occurred in Astro's TypeScript compatibility check. Evidence and task-boundary guidance are in docs/performance.md. The external repository was inspected without modifying it.

Hosted run 36906004644 passed on bec821233e1298f01383c461381dd5d2f2c64f23: validation, Node/Bun/language-neutral mise consumers, native Go test/lint/security, GoReleaser snapshot, Aube, Docker validation, all three Neovim adapters, artifact handoff and the aggregate gate. Mise setup took 3-5 seconds; Neovim installation took 2 seconds. Cold scanner compilation took 19 seconds; the final audit added a pinned binary cache with opt-in trusted writes, serialized Docker publication and fixed multiline Go/Aube artifact paths. Local checks pass all 38 contracts after those additions. Hosted run 36906625031 passed all 38 contracts and every consumer on 2636041ec6ee4a3159d110a26fa3299c3d6b7215. The final formula audit additionally corrected nested archive binary test paths; its regression and final branch revision are validated by the same required suite.

Verification limits: no real Cloudflare deployment, GHCR publication, tap push, production release, infra dispatch or Tailscale policy apply is performed. Their guards/payloads/formula generation/tag publisher are checked locally; external credential, environment-protection and receiver configurations remain operator prerequisites. Hosted consumers cover Linux x64. macOS/ARM assets and self-hosted provisioning are documented but not executed in this suite. Application cold/warm performance needs representative consumer runs; fixture timings prove the setup contract only.

## Execution

1. Implement contracts and shared policy validation; remove obsolete audit tooling.
2. Update specialized workflows and fixtures.
3. Add executable regression/consumer checks and complete documentation.
4. Run targeted tests, full local checks, and hosted checks; review diff against every requirement.

Use scripts only for repository self-validation; remote reusable workflows must execute without checking out this library's scripts or configuration. Keep unrelated remote changes intact. Preserve an explicit list of external verification limits; never call mocked publishing a real deployment.
