# Migration to the next major workflow contract

These changes are staged for the next major release. They are not available on existing v1/v2/v3 tags. Test callers against the implementation commit SHA before adopting the future `v4` tag. Pin an immutable reviewed SHA when repeatability matters; floating major tags accept compatible updates.

| Previous behavior | New contract | Caller change |
| --- | --- | --- |
| Universal CI with every phase disabled succeeds without checks | Runs the repository-owned `ci` task | Define `tasks.ci` or enable explicit task flags |
| Library root mise tasks were implicitly expected by Go adapters | Go adapters execute native commands directly | Remove `go-*` library task assumptions; set `working-directory` |
| Universal working-directory did not affect all operations | Tasks, tool setup, cache discovery and artifact paths use the directory | Move directory-specific commands/configuration into that project |
| Separate mise processes per enabled phase | One graph; shared dependencies execute once | Declare `depends` for install/build ordering; set `task-jobs` when safe |
| Reusable jobs shared concurrency based on the caller workflow | CI cancellation is caller-owned | Remove `cancel-in-progress` and `concurrency-suffix`; add caller concurrency if desired |
| Aube silently skipped missing enabled scripts; floated Aube | Missing scripts fail; Aube pinned; tracked lockfile required and clean by default | Disable unused checks explicitly; commit a supported lockfile; specify ambiguous lockfiles |
| Cloudflare built JavaScript and attempted an undocumented token exchange | Deploys an earlier same-run artifact using a Pages API token | Build separately, pass `artifact-name`, supply `CLOUDFLARE_API_TOKEN`; remove package-manager/build/OIDC inputs |
| Docker always authenticated and used shared cache/dual architectures | `push:false` needs no credential; native default; scoped cache; attestations enabled | Select architectures explicitly; opt into `load` or an exporter for validation output |
| Generic dispatcher inferred vars.APP_ID | Explicit dispatch-app-id and trusted source branch | Supply the App ID as an input and install the App only on the target |
| Homebrew required all four archives and assumed `version` CLI argument | Optional per-platform assets, explicit test-args, Ruby validation | Omit unsupported assets; set test-args as needed; token absence fails by default |
| Neovim version meant an apt package; mini ref could float | Exact release/nightly and immutable mini commit | Use a release tag for Neovim and a full SHA for mini-version |
| Lockfile sync could write any PR branch | Trusted author and release branch; read-only generation, isolated artifact publication | Set release-pr-author for your release identity; configure release-branch-prefix and packageManager or pnpm-version |
| Tool caches saved implicitly | Go/universal cache writes opt in on trusted default-branch runs | Enable save-cache on one designated writer |
| PR jobs could automatically restore trusted dependency/build/tool caches | Fork PRs skip those restores; same-repository PRs retain them | Use `cache: false` for private dependency source; leave saves off and delete sensitive existing caches, because GitHub cache access itself is not isolated from forks |
| Release/tag advancement independent of tests | Full suite gates release; floating tag target must equal the tested SHA | Configure the protected release environment and tag credential |

Repository maintenance now uses `mise run setup` once and `mise run ci` thereafter. The old exported Go/Node/Bun helper tasks, duplicated inline validator, gh-aw bootstrap, and monthly documentation audit are removed. Validation discovers every Python contract test automatically. Caller examples and generated-reference contracts are checked during normal CI instead of a scheduled audit.

`request-app-deploy.yml` remains the convenient dispatcher for matt-riley/infra. The generic `request-infra-deploy.yml` supports other owners/targets. Both preserve source SHA and artifact run ID as strings and report dispatch acceptance; they do not claim that a remote deployment completed.

Luacheck asset bytes are verified against a pinned SHA-256 before execution. When overriding `luacheck-version`, also pass the matching reviewed `luacheck-sha256`. GoReleaser snapshots use a separate read-only job; publication retains its write permission and release environment.

StyLua and the default Neovim release also verify pinned per-platform archive digests before extraction. Pair `stylua-version` overrides with `stylua-sha256`, and nondefault stable `neovim-version` overrides with `neovim-sha256`. Intentional Neovim nightly runs verify GitHub's current asset SHA-256 metadata unless an explicit digest is supplied. Neovim init/collection errors and empty test sets now fail immediately, and the workflow owns the headless reporter so consumer configuration cannot leave CI running indefinitely.

Homebrew `tag` and Docker `tag-name` must match the triggering tag ref when publishing a versioned release. Default-branch Docker publishing without `tag-name` still produces a SHA tag. Lockfile sync rejects directory/symlink targets; custom install commands must produce the selected regular lockfile. Universal extra `cache-paths` resolve from `working-directory`, while absolute and home-relative paths remain supported; dependency and Go build caches use separate fallback namespaces.

Aube retains its GitHub-token registry fallback; `node_auth_token` is an optional override. Configure private Go module authentication in Universal repository tasks with `dependency-token`; native adapters do not persist checkout credentials for dependency resolution. Optional Homebrew publishing (`fail-if-missing-token: false`) skips before downloading release assets when no tap token exists. Release Please normalizes its empty target to the default branch for concurrency; Tailscale tests use separate run/attempt groups, while all applies in one repository share a bounded max queue, including default and explicit tailnet selectors.

Aube lockfiles must have a supported filename and be regular nonsymlink files inside the repository, selected with relative paths without `..`. Clean-lockfile validation compares actual bytes and the executable bit before/after install, independent of changes to Git's index or HEAD. When supplying Aube `coverage-path`, also supply a unique `coverage-artifact-name` for each call/matrix entry; coverage can come from build output even when tests are disabled. Artifact paths may select repository children, but cannot select the whole checkout root. Go overrides containing only whitespace cannot stand in for a check. Pages locks apply to the project independently of the caller's chosen protected environment.

Docker version tags require valid SemVer components, including the rules for numeric prerelease identifiers. GoReleaser publish-mode `args` must not request snapshots/auto-snapshots/help or skip publishing; select `snapshot: true` for nonpublishing validation. Tap App authentication may fall back to the supplied legacy PAT; missing-token policy still controls whether Homebrew is skipped or the release fails. Tailscale's `environment` now protects apply runs only, so its federation trust configuration must also authorize the environment-free test context. This can change the OIDC subject; review the actual repository's configured claims before adopting the SHA.

Neovim nightly remains an explicit floating compatibility option. Its GitHub metadata digest checks asset consistency, not protection against a publisher replacing both the archive and its metadata. Supply an independently reviewed `neovim-sha256` when a fixed nightly asset is required, or use the default pinned stable release.

Docker's explicit `outputs: type=docker,...` follows the same single-platform and disabled-attestation contract as `load: true`. Other compatible exporters retain requested attestations. The hosted suite exercises both Docker load and explicit Docker export with the default attestation inputs.

Docker publishing now uses GitHub queue:max to retain up to 100 pending publications per image instead of replacing the existing pending tag. Queue overflow still cancels additional jobs, and FIFO refers to the order jobs start waiting, not tag dispatch order. The local check entrypoint validates this newer key explicitly because the pinned actionlint predates it.

Docker now skips automatic BuildKit restores for fork PRs. `cache: false` disables both restore and export; publishing otherwise continues to write its scoped cache. Build-only callers can opt into `save-cache: true` for default-branch push/manual runs. Designate one writer and never cache sensitive source or credentials. Artifact names are validated before builds using the upload backend's forbidden-character rules; use `server-coverage` rather than `packages/server-coverage`. Spaces and Unicode remain supported.

Go/Aube now share Universal's early retention policy: supply an explicit positive integer within `GITHUB_RETENTION_DAYS`. Zero/repository-default and above-cap automatic clamping are deliberately outside this API. Universal cache saves follow required artifact uploads, so missing output prevents cache writes.

Homebrew uses queue:max per tap to retain up to 100 pending formula publications, matching Docker's bounded publication policy. Queue overflow remains a cancellation risk.

Universal dependency-cache identity includes the resolved cache-path set (including browser opt-in and exclusions). A changed path set gets a new namespace and cannot restore an archive for the previous set; merely reordering paths preserves identity. Advisory Go lint failures do not save module/build caches; the lint cache is managed explicitly with the same successful-outcome guard, and the action's unconditional post-save is disabled.

Homebrew publication retries nonconflicting cross-repository tap updates using ordinary pushes and rebases, stopping on a same-formula conflict. GitHub locks are repository-scoped: choose one publisher repository per Docker image, and configure external deployment ownership where multiple repositories target a shared service. Self-hosted Neovim runners need gh, Python 3, Git and the appropriate archive tools; no apt provisioning is added. pnpm sync requires packageManager: pnpm@<version> or explicit pnpm-version, and now checks this before package-manager setup. Manual Tailscale apply must select the default branch.

Empty working-directory inputs now select `.` consistently in Universal, Aube, Neovim and Go adapters, including tool setup and cache hash patterns. Configured artifact path lists must contain at least one inclusion; whitespace-only and exclusion-only selections fail before setup.

Tailscale skips fork PR authentication; validate those changes only after maintainer review in a trusted context. Applies share one repository queue for all tailnet selectors; use one authoritative publisher repository per tailnet across repositories.

Homebrew formula generation trusts the chosen source release publisher. Its recorded archive checksum detects later byte changes, not an initially compromised producer. Verify any required producer attestations before invoking the publisher; generated formulas receive Ruby syntax validation, not a cross-platform installation test in this workflow.


PNPM lockfile sync now requires an explicit release-pr-author input in addition to same-repository/prefix checks. Configure the exact login used by your Release Please App/PAT; the workflow no longer assumes github-actions[bot]. The caller only needs contents:read; the supplied push token still needs contents:write. Custom commands and pnpmfile hooks execute in the read-only generation job without that secret. A changed regular lockfile is uploaded for one day and passed by artifact ID to a fresh checkout at the original PR head SHA; the isolated publisher disables Git hooks, isolates Python imports from checked-out modules and commits only that file. Unchanged generation skips artifact upload and the publication job.

runner now selects the generation runner; publish-runner defaults independently to ubuntu-latest. Publication requires an ephemeral runner isolated from generation processes/filesystem. A shared persistent self-hosted machine is not a security boundary, even with a new checkout directory. Generation and publication serialize together per PR branch with a bounded max queue. The existing package lifecycle --ignore-scripts flag remains; pnpmfile hooks may still run, as documented by pnpm, so custom resolution hooks remain usable without publication credentials.

Lockfile generation validates the repository-relative working directory and resolved package.json before reading it, including with an explicit pnpm-version. Publication requires the branch to retain the original PR head through an atomic expected-head lease; branch advances, rewinds and deletions skip stale updates with status superseded instead of restoring discarded commits. A failed push is only superseded after an authenticated remote read proves the branch changed or was deleted; unchanged-head push failures and failed remote verification remain errors. The published lockfile commit must be a direct child of the original head.

Homebrew formula generation supports public source repositories with anonymously downloadable release assets. Private/internal sources now fail before download or formula generation because authentication in CI does not make the generated release URL available to Homebrew users.

Universal cache discovery skips an automatic ecosystem cache when its tool is unavailable before tasks execute, including an uninitialized package-manager shim. Declare the tool in mise for automatic discovery, or supply explicit cache-paths when the install task provisions it later. Consumer task failures remain failures.

Aube accepts an explicit parent-relative lockfile-path such as ../../pnpm-lock.yaml for workspace-root lockfiles, while requiring a tracked regular nonsymlink file inside the repository. GoReleaser publications use queue:max, retaining up to 100 pending runs under the same bounded queue policy as Docker/Homebrew.

The dispatch workflows retain string inputs for artifact-run-id and emit a JSON number for client_payload.artifact_run_id, preserving the existing generic infra payload contract. Neovim nightly resolves the asset ID and SHA-256 from one metadata snapshot and downloads that ID, with at most one fresh-snapshot retry. Stable and explicitly reviewed hashes remain mandatory checksum checks before extraction.

Homebrew permits three nonconflicting recovery rebases, with a final fourth push. Exhausting the push budget stops immediately; the job no longer performs a final rebase whose result cannot be pushed.


Caller-supplied reviewed SHA-256 inputs take precedence over built-in digest fallbacks, including the default Neovim release. Leave the override empty to use the default per-platform pin; supply a digest appropriate to the selected platform when overriding it. Caller configuration is trusted and owns that reviewed value.

Release Please uses queue:max per normalized target branch, retaining up to 100 pending callers, including distinct config/manifest files. Same-repository Tailscale pull_request_target validation pins the proposed PR head instead of testing the base policy; fork authentication remains skipped and PR contexts cannot apply.

PNPM packageManager must declare an exact SemVer, with optional prerelease/build metadata; malformed pnpm@ prefixes fail before setup. The explicit pnpm-version override retains the pinned setup action's npm version/range/tag support. After mise run setup, regenerate reference documentation with mise run reference; rendered table cells normalize CRLF, CR and LF.

GoReleaser rejects enabled help flags in snapshot and publication modes, so help output cannot substitute for a release check. Floating-major repair rejects stable tags with leading-zero numeric components. Tailscale policy-file must be relative and resolve inside the checkout; symlinks that remain inside the checkout are supported, while escaping symlinks and host paths fail before the ACL action. Reference generation supports scalar/list workflow_call shorthand as well as mapping declarations. Self-hosted Tailscale runners need Python 3 for path validation. The local Neovim prepare harness requires gh authentication or GH_TOKEN inherited from the parent environment.
