# Complete caller examples

Replace REVIEWED_COMMIT_SHA with a tested full commit SHA. These target the next major API; existing tags have different contracts. Adapt repository/project/asset names and prerequisites below before use. All examples declare their maximum required permissions; publishing credentials are never implicitly inherited.

## ci.yml

Define tasks.ci and the required tools in your mise.toml, as shown in README.

```yaml
name: Universal CI
'on':
  pull_request: null
permissions:
  contents: read
jobs:
  run:
    uses: matt-riley/matt-riley-ci/.github/workflows/ci.yml@REVIEWED_COMMIT_SHA
    with:
      task-jobs: 4
```

## go-ci.yml

Commit go.mod. go-version-file defaults to working-directory/go.mod; coverage requires test-args that generate the chosen file.

To fail the job below a minimum total statement coverage, add `coverage-threshold` (a percent above 0 and at most 100; the default `0` disables the gate). It reads the Go profile named by `coverage-path`, so also set `coverage-artifact-name` and make `test-args` (or `test-command`) write that profile. It uses the `total:` figure from `go tool cover -func`, the same number the per-repository gates in hopcli, newbrew and mediacreator compute, and fails only when the total is strictly below the threshold.

```yaml
    with:
      test-args: -coverprofile=coverage.out
      coverage-path: coverage.out
      coverage-artifact-name: go-coverage
      coverage-threshold: 71
```

```yaml
name: Go CI
'on':
  pull_request: null
permissions:
  contents: read
jobs:
  run:
    uses: matt-riley/matt-riley-ci/.github/workflows/go-ci.yml@REVIEWED_COMMIT_SHA
```

Set `run-verify: true` to run `go mod verify`, and `run-tidy: true` to fail when `go mod tidy` would change `go.mod` or `go.sum` (the diff is printed and the files are restored afterwards, so later steps see your committed files). Both default to off and run in `working-directory`.

## go-lint.yml

Commit go.mod and a compatible .golangci.yml when using custom lint configuration.

```yaml
name: Go Lint
'on':
  pull_request: null
permissions:
  contents: read
jobs:
  run:
    uses: matt-riley/matt-riley-ci/.github/workflows/go-lint.yml@REVIEWED_COMMIT_SHA
```

## go-security.yml

Commit go.mod. Private module credentials, if needed, belong in a repository-owned Universal CI task.

```yaml
name: Go Security
'on':
  pull_request: null
permissions:
  contents: read
jobs:
  run:
    uses: matt-riley/matt-riley-ci/.github/workflows/go-security.yml@REVIEWED_COMMIT_SHA
```

## aube-ci.yml

Commit package.json with a test script and one supported regular lockfile. Enable lint/build only when those scripts exist. To upload coverage, pass `coverage-path` and a unique `coverage-artifact-name` for each call/matrix entry; build-generated coverage is supported when tests are disabled.

```yaml
name: Aube CI
'on':
  pull_request: null
permissions:
  contents: read
  packages: read
jobs:
  run:
    uses: matt-riley/matt-riley-ci/.github/workflows/aube-ci.yml@REVIEWED_COMMIT_SHA
    with:
      run-lint: false
```

## docker-ghcr-publish.yml

Commit Dockerfile. Select platforms explicitly for cross-platform publishing. For PR validation set push:false and omit tag-name. Both load:true and outputs containing type=docker require a single platform and automatically disable attestations unsupported by the Docker exporter. Other compatible exporters and publishing retain attestations by default.

```yaml
name: Docker GHCR Publish
'on':
  push:
    tags:
    - v*
permissions:
  contents: read
  packages: write
jobs:
  run:
    uses: matt-riley/matt-riley-ci/.github/workflows/docker-ghcr-publish.yml@REVIEWED_COMMIT_SHA
    with:
      tag-name: ${{ github.ref_name }}
```

## cloudflare-pages-deploy.yml

Create the Pages project first. Supply an account-scoped Pages edit token. Configure its production branch and protect the production GitHub environment.

```yaml
name: Cloudflare Pages Deploy
'on':
  push:
    branches:
    - main
  workflow_dispatch: null
permissions:
  contents: read
jobs:
  build:
    uses: matt-riley/matt-riley-ci/.github/workflows/ci.yml@REVIEWED_COMMIT_SHA
    with:
      task: build
      artifact-path: dist
      artifact-name: site
  deploy:
    uses: matt-riley/matt-riley-ci/.github/workflows/cloudflare-pages-deploy.yml@REVIEWED_COMMIT_SHA
    with:
      project-name: my-site
      artifact-name: site
    secrets:
      CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
      CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
    needs: build
```

## go-goreleaser.yml

Commit go.mod and .goreleaser.yaml/.yml. Protect the release environment. Optional tap credentials use tap-app-id/private-key or homebrew-tap-token; a failed App token can fall back to the supplied PAT. Missing credentials skip only Homebrew unless configured to fail. For PR validation set snapshot:true and use pull_request; publish mode rejects snapshot/auto-snapshot/help flags and skipping publish.

```yaml
name: Go GoReleaser
'on':
  push:
    tags:
    - v*
permissions:
  contents: write
jobs:
  run:
    uses: matt-riley/matt-riley-ci/.github/workflows/go-goreleaser.yml@REVIEWED_COMMIT_SHA
```

## homebrew-formula.yml

Create the release and upload the configured archive before this call. Each archive must contain the binary at the declared path. The tap token needs contents write on the tap; github-token is optional for private source releases. Other platform archives are optional.

```yaml
name: Homebrew Formula
'on':
  push:
    tags:
    - v*
permissions:
  contents: read
jobs:
  run:
    uses: matt-riley/matt-riley-ci/.github/workflows/homebrew-formula.yml@REVIEWED_COMMIT_SHA
    with:
      tag: ${{ github.ref_name }}
      formula-name: tool
      class-name: Tool
      desc: Example tool
      homepage: https://github.com/owner/tool
      binary: tool
      tap-repo: owner/homebrew-tools
      archive-x86_64-linux: tool_linux_amd64.tar.gz
    secrets:
      homebrew-tap-token: ${{ secrets.HOMEBREW_TAP_TOKEN }}
```

## nvim-format.yml

Commit lua/, plugin/ and tests/, or set paths to the paths that actually exist. Quoted paths support spaces. Pair stylua-version overrides with the matching per-platform stylua-sha256; default archives are checksum-pinned.

```yaml
name: Neovim Format (stylua)
'on':
  pull_request: null
permissions:
  contents: read
jobs:
  run:
    uses: matt-riley/matt-riley-ci/.github/workflows/nvim-format.yml@REVIEWED_COMMIT_SHA
```

## nvim-lint.yml

The default luacheck asset is checksum-pinned. Pair any version override with a reviewed `luacheck-sha256`.

Commit Lua sources and optional .luacheckrc. Only Linux x64 has a supported standalone luacheck binary.

```yaml
name: Neovim Lint (luacheck)
'on':
  pull_request: null
permissions:
  contents: read
jobs:
  run:
    uses: matt-riley/matt-riley-ci/.github/workflows/nvim-lint.yml@REVIEWED_COMMIT_SHA
```

## nvim-typecheck.yml

Opt-in LuaLS typecheck, as pint.nvim and slides.nvim run today. It installs a pinned, checksum-verified lua-language-server (`luals-version` / `luals-sha256`, Linux x64) and the pinned Neovim used by nvim-tests.yml, exports that Neovim's runtime as `VIMRUNTIME` (so `"$VIMRUNTIME/lua"` in `.luarc.json` resolves), and runs `lua-language-server --check=<check-path> --checklevel=<checklevel> --check_format=json`. Any reported diagnostic fails the job and is printed; a missing result file or a LuaLS crash also fails. Configure globals, libraries and ignored directories in the consumer's `.luarc.json`. Defaults: `check-path: .`, `checklevel: Warning`.

```yaml
name: Typecheck
'on':
  pull_request: null
permissions:
  contents: read
jobs:
  run:
    uses: matt-riley/matt-riley-ci/.github/workflows/nvim-typecheck.yml@REVIEWED_COMMIT_SHA
```

## nvim-tests.yml

Commit tests/minimal_init.lua that appends os.getenv("MINI_PATH") to runtimepath, calls require("mini.test").setup(), and appends the consumer repository to runtimepath. Commit nonempty test*.lua test sets. Set minimal-init/test-directory when paths differ. The workflow supplies its CI reporter and fails init/collection errors. Pair stable release overrides with neovim-sha256; nightly uses GitHub asset metadata by default.

```yaml
name: Neovim Tests (mini.test)
'on':
  pull_request: null
permissions:
  contents: read
jobs:
  run:
    uses: matt-riley/matt-riley-ci/.github/workflows/nvim-tests.yml@REVIEWED_COMMIT_SHA
```

## nvim-docs.yml

Opt-in: regenerate a plugin's vim help and commit it. It installs the pinned Neovim and mini.nvim exactly like nvim-tests.yml, runs `docs-command` (default `make docs`, with `MINI_PATH` pointing at the pinned mini.nvim checkout) from working-directory, then commits what changed under `file-pattern` (default `.`; use `doc/*.txt` to limit it) as github-actions[bot] with `commit-message` (default `chore(docs): regenerate vim help`) and pushes to the current branch. Nothing is committed for events other than push and workflow_dispatch, for `commit: false`, or when nothing changed. The push uses the workflow token, so it does not start further runs; pass a `token` secret with contents write if the branch needs another identity. The generator step never sees the push token. Path filters and concurrency belong in the caller; pushes are never forced, so give the caller a concurrency group to avoid a rejected push.

```yaml
name: Docs
'on':
  push:
    branches: [main]
    paths: ['lua/**', 'plugin/**', 'Makefile']
  workflow_dispatch: null
permissions:
  contents: read
concurrency:
  group: docs-${{ github.ref }}
  cancel-in-progress: true
jobs:
  run:
    permissions:
      contents: write
    uses: matt-riley/matt-riley-ci/.github/workflows/nvim-docs.yml@REVIEWED_COMMIT_SHA
```

## pnpm-lockfile-sync.yml

Only same-repository PRs matching both the release-please-- branch prefix and the required release-pr-author run. Set the exact App/PAT author login used by your release automation; use github-actions[bot] only for PRs actually opened by that identity. Replace the example's release-automation[bot] with your configured login. Commit package.json with packageManager: pnpm@<version>, or set pnpm-version. Generation runs with a read-only token and no push secret; changed lockfile bytes pass through a same-run artifact to a fresh checkout on an isolated ephemeral publish-runner (ubuntu-latest by default). The supplied token needs contents write; App/PAT credentials permit subsequent push-triggered CI. Custom install commands and pnpmfile hooks stay in the generation job. A stale run whose branch moved or was deleted reports superseded; authentication/network failures remain errors.

```yaml
name: PNPM Lockfile Sync
'on':
  pull_request: null
permissions:
  contents: read
jobs:
  run:
    uses: matt-riley/matt-riley-ci/.github/workflows/pnpm-lockfile-sync.yml@REVIEWED_COMMIT_SHA
    with:
      release-pr-author: 'release-automation[bot]'
    secrets:
      token: ${{ secrets.RELEASE_PR_TOKEN }}
```

## release-please.yml

Commit release-please-config.json and .release-please-manifest.json. Configure repository settings to allow Actions to create PRs. Gate this job on your own checks. Pass token: secrets.RELEASE_TOKEN if release bot events must trigger further workflows.

```yaml
name: Release Please
'on':
  push:
    branches:
    - main
  workflow_dispatch: null
permissions:
  contents: write
  issues: write
  pull-requests: write
jobs:
  check:
    uses: matt-riley/matt-riley-ci/.github/workflows/ci.yml@REVIEWED_COMMIT_SHA
    permissions:
      contents: read
  release:
    uses: matt-riley/matt-riley-ci/.github/workflows/release-please.yml@REVIEWED_COMMIT_SHA
    needs: check
```

## release-please-dispatch.yml

Opt-in follow-on that replaces the thin `dispatch-goreleaser` job many consumers copy. Tags created with the default GITHUB_TOKEN do not start tag-triggered workflows, but `workflow_dispatch` is still allowed, so after a release this job runs `gh workflow run <workflow> --ref <tag>` (`workflow` defaults to `goreleaser.yml`; use it for `homebrew.yml` or a Docker publisher too). It is a separate workflow rather than an input of release-please.yml because a reusable workflow's job permissions must fit inside the caller's grant: adding `actions: write` to release-please.yml would stop every existing caller from starting. The calling job therefore grants `actions: write` itself. Pass the same release token as the optional `release-token` secret (empty when absent): when it is set its tag push already starts the publisher and nothing is dispatched. No new secret is introduced and the token is only checked for presence. The dispatched workflow must accept `workflow_dispatch`. Use `needs` for anything that must finish first (for example a build and publish job).

```yaml
name: Release
'on':
  push:
    branches: [main]
permissions:
  contents: read
jobs:
  release-please:
    permissions:
      contents: write
      issues: write
      pull-requests: write
    uses: matt-riley/matt-riley-ci/.github/workflows/release-please.yml@REVIEWED_COMMIT_SHA
    secrets:
      token: ${{ secrets.RELEASE_PLEASE_TOKEN || secrets.GITHUB_TOKEN }}
  dispatch:
    needs: release-please
    permissions:
      contents: read
      actions: write
    uses: matt-riley/matt-riley-ci/.github/workflows/release-please-dispatch.yml@REVIEWED_COMMIT_SHA
    with:
      release-created: ${{ needs.release-please.outputs.release_created }}
      tag: ${{ needs.release-please.outputs.tag_name }}
      workflow: goreleaser.yml
    secrets:
      release-token: ${{ secrets.RELEASE_PLEASE_TOKEN }}
```

## request-app-deploy.yml

Install a contents-write dispatch App only on matt-riley/infra. Add this job after successful build/test jobs. The app identifier must be allowlisted by the receiving infrastructure repository.

```yaml
name: Request application deployment
'on':
  push:
    branches:
    - main
  workflow_dispatch: null
permissions:
  contents: read
jobs:
  run:
    uses: matt-riley/matt-riley-ci/.github/workflows/request-app-deploy.yml@REVIEWED_COMMIT_SHA
    with:
      app: my-app
      dispatch-app-id: ${{ vars.INFRA_DISPATCH_APP_ID }}
    secrets:
      INFRA_DISPATCH_PRIVATE_KEY: ${{ secrets.INFRA_DISPATCH_PRIVATE_KEY }}
```

## request-infra-deploy.yml

Install a contents-write dispatch App only on the target repository. Gate this job on build/test. Artifact mode requires run ID, name and digest together; run IDs are strings.

```yaml
name: Request Infra Deploy
'on':
  push:
    branches:
    - main
  workflow_dispatch: null
permissions:
  contents: read
jobs:
  run:
    uses: matt-riley/matt-riley-ci/.github/workflows/request-infra-deploy.yml@REVIEWED_COMMIT_SHA
    with:
      app-name: my-app
      infra-repo: owner/infra
      dispatch-app-id: ${{ vars.INFRA_DISPATCH_APP_ID }}
    secrets:
      PRIVATE_KEY: ${{ secrets.INFRA_DISPATCH_PRIVATE_KEY }}
```

## release-publish-npm.yml

Opt-in follow-on that replaces the `publish-typescript-client` (flagz) and `publish-package` (agent-skills) jobs. It checks out `ref` (pass release-please's `tag_name`, or `component_tag_name` for a monorepo package), sets up Node with `registry-url` (default GitHub Packages) and `scope` (default: the repository owner), and, when `ref` is set and `verify-version` is true, requires the ref to end with the `package.json` version. `install-command` and `build-command` (both empty by default) run first without any publish credential; only the final `npm publish` step receives `NODE_AUTH_TOKEN`, which is the optional `token` secret or else the workflow's GITHUB_TOKEN, so the default needs `packages: write` on the calling job and no new secret. Pass `token` only to publish to a registry that needs its own token. `access`, `dist-tag` and `dry-run` map to npm publish flags (`dry-run` packs and checks without publishing). Provenance and OIDC trusted publishing are not offered: both would force every caller to grant `id-token: write`.

```yaml
name: Release
'on':
  push:
    branches: [main]
permissions:
  contents: read
jobs:
  release-please:
    permissions:
      contents: write
      issues: write
      pull-requests: write
    uses: matt-riley/matt-riley-ci/.github/workflows/release-please.yml@REVIEWED_COMMIT_SHA
    with:
      component-output-key: clients/typescript
  publish:
    needs: release-please
    if: ${{ needs.release-please.outputs.component_release_created == 'true' }}
    permissions:
      contents: read
      packages: write
    uses: matt-riley/matt-riley-ci/.github/workflows/release-publish-npm.yml@REVIEWED_COMMIT_SHA
    with:
      ref: ${{ needs.release-please.outputs.component_tag_name }}
      working-directory: clients/typescript
      install-command: npm ci
      build-command: npm run build
```

## tailscale-acl.yml

Configure the Tailscale federated identity and restrict source workflow/repository/branch claims. Commit policy.hujson. Same-repository PRs validate; fork PRs skip authenticated checks and are validated after trusted maintainer review. Default-branch pushes apply. Protect apply through the environment input and Tailscale identity policy. The protected environment is bound only to applies; authorize the appropriate environment-free test context as well. [GitHub OIDC subjects](https://docs.github.com/en/actions/reference/security/oidc#example-subject-claims) differ between environment jobs and PR/branch jobs; use the actual subject format configured for your repository.

```yaml
name: Tailscale ACL
'on':
  pull_request: null
  push:
    branches:
    - main
permissions:
  contents: read
  id-token: write
jobs:
  run:
    uses: matt-riley/matt-riley-ci/.github/workflows/tailscale-acl.yml@REVIEWED_COMMIT_SHA
    with:
      oauth-client-id: ${{ vars.TS_CLIENT_ID }}
      audience: ${{ vars.TS_AUDIENCE }}
```
