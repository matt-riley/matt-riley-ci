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

## pnpm-lockfile-sync.yml

Only same-repository PRs with a release-please-- branch prefix run. Commit package.json with packageManager: pnpm@<version>, or set pnpm-version. The token needs contents write; App/PAT credentials permit subsequent push-triggered CI.

```yaml
name: PNPM Lockfile Sync
'on':
  pull_request: null
permissions:
  contents: write
jobs:
  run:
    uses: matt-riley/matt-riley-ci/.github/workflows/pnpm-lockfile-sync.yml@REVIEWED_COMMIT_SHA
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
