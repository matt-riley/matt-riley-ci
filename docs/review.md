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

The checked-in suite verifies Linux x64 consumers and 57 executable contracts, including real mise graphs, Ruby syntax and local Git publication. Seven additional real Neovim exit-status cases run in hosted validation and were also exercised locally with the pinned macOS ARM64 release. Hosted checks exercise Go test/lint/security, GoReleaser snapshots, Aube, Node/Bun/language-neutral mise tasks, Docker validation, Neovim tools/tests, the no-credential Homebrew skip and artifact handoff.

Production Cloudflare/GHCR/tap/release/dispatch/Tailscale operations are not exercised using live write credentials. Operators must configure environments, App permissions, registry/service access, branch protection and receiving infrastructure policy. The receiver must verify source and artifact provenance; dispatch acceptance does not prove deployment completion. macOS/ARM execution and self-hosted provisioning also need real consumer validation before relying on them.

My assessment: this is a sound small workflow library after these changes, with a clearer standard contract and materially less unnecessary work. It should remain deliberately modest. Add ecosystem-specific caching/adapters only when real consumers justify them; add clean consumer and negative cases alongside each new adapter. Treat these changes as a major upgrade, test a pinned implementation SHA, and do not silently move existing v1/v2/v3 APIs to this contract.

## Full PR follow-up audit

The follow-up examined the complete change against main: all 17 public workflows, repository release/validation workflows, policy/reference scripts, consumer fixtures, regression tests, caller examples, migration/performance documentation, and the removal of agentic audit/bootstrap files. The review checked runtime behavior, permissions/secrets, event authority, concurrency, cache matching, path/argument boundaries, outputs, public defaults, and documentation consistency. Green sample jobs did not count as proof of unexecuted writer paths.

| Finding | Disposition and verification |
| --- | --- |
| Homebrew could download one release while triggered by another tag; a binary of `.` could mean a directory. | Fixed exact tag/ref matching and binary path validation; executable formula tests cover mismatches and directory inputs. |
| Lockfile sync accepted `.`/`..` and named directories. | Both guards reject dot components; commit requires a regular nonsymlink file. A real local Git remote verifies only the lockfile is committed/pushed, and unchanged runs remain successful. |
| Universal dependency fallback prefixes also matched Go build caches. | Split cache namespaces; test confirms build keys cannot match the dependency fallback. [GitHub selects prefix matches by recency](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching#cache-key-matching), so this was a real collision, not merely naming style. |
| Extra cache paths ignored a nested working directory. | Resolve relative paths from the consumer project while preserving absolute/home paths; executable metadata checks cover each form. |
| Neovim's default reporter correctly handles test failures, but init/collection errors or empty sets can hang before reporting. | Reproduced all three hangs, then added guarded collection, nonempty checks and an explicit quitting reporter. Seven real cases cover success, assertion/runtime/init/collection errors, empty sets and a custom nonquitting reporter. |
| Major-tag remote reads lacked credentials for private repositories; separate reads could pair stale ancestry with a newer lease object. | Authenticate fetch/read/push transiently and derive the object/peeled commit from one remote snapshot. Existing real-Git tag tests and command-boundary/lease tests cover both changes. |
| Pages directory and Aube script inputs accepted option-like values. | Reject leading hyphens so `--help` cannot silently replace deployment/test execution; negative command tests cover these cases. |
| Docker could publish a version tag unrelated to its event ref. | Require matching tag refs for versioned publishing; retain default-branch SHA publishing and credential-free validation. |
| StyLua/Neovim archives lacked the checksum guard already added to luacheck. | Pin default per-platform digests, require reviewed digests for stable version overrides, and verify nightly metadata before extraction. Tests prove mismatches stop extraction and PATH exposure. |
| Local caller policy checked permissions but missed unsupported job keys and input contracts. | Validate callable targets, supported caller keys, required/unknown inputs and literal types; mutation tests include misplaced environments and string/boolean mismatches. |
| Review claimed the release caller had an unsupported job-level environment. | Not valid: `environment: release` is inside `with`; the called job binds it. A regression verifies both placements. [GitHub's supported caller keys](https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations#supported-keywords-for-jobs-that-call-a-reusable-workflow) confirm that distinction. |

Pinned upstream GoReleaser skip flags and Docker metadata prerelease behavior were checked against their source; they did not need changes. Earlier valid Aube authentication and infra repository fixes remain covered. No real production publication, protected-environment approval, or receiver-side deployment was performed. A thorough review and regressions reduce missed defects; they cannot guarantee that future reviewers will never identify another issue.

## Late review findings

Faultline subsequently exposed 35 findings against the earlier `91ebbb9` revision. The table covers every visible finding, numbered in the order of that review-status comment. At inspection the review was paused/incomplete, with 44 retained findings and nine omitted from the visible comment; those nine cannot be assessed from the published text. This assessment is not a claim that Faultline completed a clean review of the final head.

| Findings | Assessment and action |
| --- | --- |
| 1, 2: Aube registry-token fallback | Valid regression. Restore `secrets.node_auth_token || github.token` for every command; verify default and override behavior. |
| 3, 4, 5: Universal artifact/tool paths ignore working directory | Incorrect: job-level `defaults.run.working-directory` applies to these shell steps. Nested consumer and executable path tests verify the documented behavior. |
| 6: Cache-path output delimiter collision | Superseded by the absolute-path resolver: a relative path named `CACHE_PATHS` becomes a full path and cannot equal the delimiter. |
| 7: Revision cache keys cause unbounded growth | Partly a performance tradeoff, not an unbounded-storage defect. GitHub caches are immutable and subject to quotas/eviction; revision keys permit fresh compiler-cache saves. Preserve compatible restore prefixes and opt-in single writers; document transfer/eviction costs and opt-out rather than freeze the first cache under a constant key. |
| 8: Wrangler lacks deployment-url output | Incorrect for the pinned action: its [action manifest](https://github.com/cloudflare/wrangler-action/blob/ebbaa1584979971c8614a24965b4405ff95890e0/action.yml) explicitly declares `deployment-url`. |
| 9: Pages project name requires another maximum-length check | No confirmed defect in the supplied evidence. The [project API](https://developers.cloudflare.com/api/resources/pages/subresources/projects/methods/create/) specifies the name pattern; the library validates that pattern. Do not invent a limit from unrelated account-ID schema fields. Service rejection remains a failed deployment. |
| 10, 11, 12: Caller requests write permissions for validation | Incorrect: reusable calls must grant the maximum permission requested by their nested definitions, including a skipped writer job. Executed snapshot/validation jobs downscope to read; hosted consumers verify the call graph. Removing the parent allowance makes GitHub reject the workflow before execution. |
| 13, 14, 15: Docker tag differs from triggering release | Valid; already fixed by exact version-tag/ref matching in the first audit batch. |
| 16: Docker accepts malformed image components | Valid. Validate the GHCR owner/image component grammar; executable cases reject empty/trailing/illegal components and accept valid nested paths. |
| 17, 19: Go version-file override needs a different cache lockfile hash | Incorrect as a correctness claim. The override selects the toolchain; runtime Go version participates in the cache identity. Dependency hashes describe the actual working-directory module being tested/linted. A separate toolchain module does not replace that module's dependency identity. |
| 18: Fork PRs restore private dependency source | Valid concern. Skip automatic dependency/build/tool restores for forks, including mise and golangci-lint caches; add complete `cache: false` controls. The guard is not a confidentiality boundary: [GitHub permits fork PRs to read base-branch caches](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching#best-practices-for-using-caches-securely). Never upload private contents that contributors must not read; disable caching and delete existing sensitive entries. |
| 20: Native Go adapters no longer inherit checkout authentication | Intentional major-version contract. Checkouts do not persist credentials; custom private-module authentication belongs in Universal repository tasks with an explicit read-only dependency secret. Document that migration rather than restore ambient credentials. |
| 21: Optional Homebrew credential absence fails during asset download | Valid. Resolve credentials before generating/downloading assets; a missing optional token reports skipped. A hosted reusable consumer asserts that output without any release assets or write credentials. |
| 22: Homebrew CLI default changes from version to --version | Intentional documented v4 change. `test-args` provides the consumer-specific override; older major tags retain their APIs. |
| 23: Whole Homebrew archive is loaded for hashing | Valid performance issue. Stream SHA-256 in bounded 1 MiB chunks before Ruby syntax validation. |
| 24: Homebrew tag/ref mismatch | Valid; already fixed and exercised with mismatched-tag tests. |
| 25, 31, 33, 34: StyLua/Neovim archives lack integrity checks | Valid against the old revision; already fixed with pinned/default and caller-supplied stable digests, checked nightly metadata, and failure-before-extraction regressions. |
| 26: Removed Neovim cancellation input breaks old callers | Intentional documented v4 API change. Caller owns CI cancellation; existing v1/v2/v3 tags are not moved to this API. |
| 27: Equivalent Release Please targets use different locks | Valid. Normalize the empty target to the default branch in the group; expression tests prove equivalence. |
| 28: Major-tag lease and ancestry use different remote snapshots | Valid; already fixed using one authenticated remote snapshot for both values. |
| 29: A Tailscale PR test replaces a queued apply | Valid. Separate test/apply groups while serializing applies to the same tailnet. Tests verify inferred/explicit action equivalence. Each group still uses default latest-pending semantics; this does not promise a lossless queue of every intermediate apply. |
| 30: Library gitignore omits consumer dist source | Incorrect scope. The library's gitignore is not installed into consumer repositories; its fixture dist directories contain generated outputs. |
| 32: Generic dispatcher lacks a trusted-branch guard | Incorrect: the job-level condition exists and requires the configured production branch and a trusted push/manual event. |
| 35: Pinned mini.nvim remote is invalid | Incorrect: `nvim-mini/mini.nvim` is the current canonical remote. Fresh pinned-commit fetches and all seven real Neovim cases succeeded locally and in hosted validation. |

The three open Copilot threads were also assessed: the Homebrew and lockfile-path findings are fixed; the release caller's environment is correctly nested under `with` and remains in place. Full local validation covers the late changes, including cache-disabled/fork/same-repository event cases, queue equivalence, malformed image paths and early optional-token handling.

A subsequent incomplete Faultline pass on `3fab374` exposed another 17 findings. These were assessed independently too:

| Findings in that pass | Assessment and action |
| --- | --- |
| 1: Aube lockfile can escape the checkout or be a symlink | Valid. Require a regular nonsymlink file under the repository; reject absolute and parent-component paths. Executable checks cover tracked links and escaping inputs. |
| 2, 3: Default Aube coverage artifact name collides | Valid for multiple calls. Remove the implicit name and require a unique explicit name when coverage is requested, matching Go's explicit naming contract; migration/examples explain matrix naming. |
| 4: Aube installation can change HEAD/index and hide lockfile modifications | Valid. Compare actual lockfile bytes against the pre-install digest instead of mutable Git status. Real Git tests reproduce a clean status after a changed-file commit and with index hiding flags; all fail the new check. |
| 5: Aube build-only coverage is omitted | Valid. Upload configured coverage after successful installation, including when tests are disabled or a later check fails; cancelled jobs do not upload. Missing configured output remains an error. |
| 6, 7, 8, 9: Universal monorepo paths/tool discovery use checkout root | Incorrect repeats: job-level run defaults apply. Preserve nested-directory execution already exercised in consumer/path tests. |
| 10: Artifact retention always caps at 90 days | The universal 90-day claim is wrong: private repositories can have a higher cap. Improve early validation against the actual `GITHUB_RETENTION_DAYS` repository cap; tests allow 100 within 400 and reject it within 90. [GitHub documents repository-specific retention](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository). |
| 11: Yarn cache path is never registered | Incorrect: `dependency_paths.append(yarn_cache)` is already present. Added executable classic/modern Yarn store checks to prove both branches. |
| 12: Different Pages environment inputs bypass project serialization | Valid. Lock by repository/project, independently of environment; this conservatively serializes all branches of that project. |
| 13: MiniTest failure exits successfully | Incorrect for the pinned explicit stdout reporter. Seven real process-level cases prove failure propagation and termination, including assertion/runtime failures and consumer reporter overrides. |
| 14: mini.nvim remote does not exist | Incorrect repeat; exact remote/commit fetch succeeds in hosted and local validation. |
| 15: Snapshot caller write allowance is unnecessary | Incorrect as a removable caller permission: nested publish definitions require it during GitHub validation; the running snapshot job has read-only permissions. Contributors with permission to edit trusted repository workflows can also edit token grants themselves; this is not a privilege newly conferred by the skipped publish definition. |
| 16: Whitespace build override can replace all Go checks | Valid. Whitespace does not count as a configured build; also reject whitespace-only test overrides. Executable negative cases cover spaces/tabs/newlines. |
| 17: Artifact paths can select the entire checkout | Valid configuration hazard. Reject the repository root across Universal/Go/Aube resolvers while retaining child directories and globs; tests run the root-directory case explicitly. |

The next incomplete status on `ef9acb1` exposed four findings: an explicit Aube lockfile could select `package.json` (valid; require a supported basename and cover a tracked package.json negative case), tracked lockfile symlinks (already fixed), and two repeat claims that Universal ignores its job-level working directory (incorrect). Every visible finding in these snapshots has an explicit disposition; incomplete and omitted review output remains a verification limit.
