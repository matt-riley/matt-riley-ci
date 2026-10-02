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
| Lockfile sync could write any PR branch | Same-repository release PR branches only; transient push credential | Set release-branch-prefix when using a different release bot; use packageManager or pnpm-version |
| Tool caches saved implicitly | Go/universal cache writes opt in on trusted default-branch runs | Enable save-cache on one designated writer |
| Release/tag advancement independent of tests | Full suite gates release; floating tag target must equal the tested SHA | Configure the protected release environment and tag credential |

Repository maintenance now uses `mise run setup` once and `mise run ci` thereafter. The old exported Go/Node/Bun helper tasks, duplicated inline validator, gh-aw bootstrap, and monthly documentation audit are removed. Validation discovers every Python contract test automatically. Caller examples and generated-reference contracts are checked during normal CI instead of a scheduled audit.

`request-app-deploy.yml` remains the convenient dispatcher for matt-riley/infra. The generic `request-infra-deploy.yml` supports other owners/targets. Both preserve source SHA and artifact run ID as strings and report dispatch acceptance; they do not claim that a remote deployment completed.

Luacheck asset bytes are verified against a pinned SHA-256 before execution. When overriding `luacheck-version`, also pass the matching reviewed `luacheck-sha256`. GoReleaser snapshots use a separate read-only job; publication retains its write permission and release environment.

StyLua and the default Neovim release also verify pinned per-platform archive digests before extraction. Pair `stylua-version` overrides with `stylua-sha256`, and nondefault stable `neovim-version` overrides with `neovim-sha256`. Intentional Neovim nightly runs verify GitHub's current asset SHA-256 metadata unless an explicit digest is supplied. Neovim init/collection errors and empty test sets now fail immediately, and the workflow owns the headless reporter so consumer configuration cannot leave CI running indefinitely.

Homebrew `tag` and Docker `tag-name` must match the triggering tag ref when publishing a versioned release. Default-branch Docker publishing without `tag-name` still produces a SHA tag. Lockfile sync rejects directory/symlink targets; custom install commands must produce the selected regular lockfile. Universal extra `cache-paths` resolve from `working-directory`, while absolute and home-relative paths remain supported; dependency and Go build caches use separate fallback namespaces.
