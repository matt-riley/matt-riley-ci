# matt-riley-ci

Reusable GitHub Actions workflows for Matt Riley repositories.

## Versioning

- Use `@v1` for non-breaking updates on the major line.
- Use `@v1.x.y` for fully pinned workflow behavior.
- Breaking changes are released under a new major tag (for example `@v2`).

## Workflows

### Universal CI

Runs standard `mise` tasks without making callers provide a task list.

```yaml
jobs:
  ci:
    uses: matt-riley/matt-riley-ci/.github/workflows/ci.yml@v1
    with:
      install: true
      lint: true
      build: false
      test: true
      vet: false
      fmt: false
      task-prefix: ""
      task-env: ""
      runner: ubuntu-latest
      timeout-minutes: 15
      cancel-in-progress: false
      concurrency-suffix: ""
      working-directory: "."
      save-cache: false
```

This workflow runs `mise run install`, `lint`, `build`, `test`, `vet`, and `fmt` when the matching boolean input is `true`. Use `task-prefix` only when a repository namespaces tasks, for example `task-prefix: "go-"` to run `go-test`, `go-vet`, and `go-fmt`. Use `task-env` for multiline task configuration such as working directories or command overrides. Repositories should declare any required runtimes or tools through `mise.toml` or `.tool-versions` so the workflow can provision them consistently.

The workflow restores dependency caches before running tasks. For Go repositories, modules and build outputs have separate lifecycles: the module cache is keyed by dependency files, while the build cache restores the newest compatible snapshot and uses the commit SHA for each new snapshot. Both keys include the runner OS, architecture, and installed Go version.

Cache writes are disabled by default. Set `save-cache: true` on exactly one comprehensive caller job; the workflow still refuses to write for pull requests, pull-request-target workflows, or non-default branches. A successful default-branch push or manual run then seeds mise, lockfile dependency, Go, and Playwright caches that later pull requests can restore.

Set `concurrency-suffix` when invoking this workflow multiple times in the same workflow file to avoid concurrency group collisions between calls.

### Go Lint

```yaml
jobs:
  lint:
    uses: matt-riley/matt-riley-ci/.github/workflows/go-lint.yml@v1
    with:
      runner: ubuntu-latest
      go-version-file: go.mod
      working-directory: .
      golangci-version: v2.10.1
      golangci-args: --timeout=5m
      continue-on-error: false
      timeout-minutes: 15
      cancel-in-progress: false
```

### Aube CI

```yaml
jobs:
  ci:
    uses: matt-riley/matt-riley-ci/.github/workflows/aube-ci.yml@v1
    with:
      node-version: "22"
      aube-version: latest
      runner: ubuntu-latest
      working-directory: .
      require-lockfile: false
      install-command: ""
      run-lint: true
      run-test: true
      run-build: false
      test-script: test
      verify-lockfile-clean: false
      lockfile-path: ""
      build-env: ""
      timeout-minutes: 15
      cancel-in-progress: false
      concurrency-suffix: ""
```

Set `concurrency-suffix` when invoking this workflow multiple times in the same workflow file to avoid concurrency group collisions between calls.

Aube reads supported lockfiles in place (`aube-lock.yaml`, `package-lock.json`, `npm-shrinkwrap.json`, `pnpm-lock.yaml`, `yarn.lock`, and `bun.lock`). If a repository contains more than one supported lockfile, set `lockfile-path` explicitly so the workflow can validate and diff the intended file.

### Cloudflare Pages Deploy

Builds a Node-based project and deploys it to Cloudflare Pages.

```yaml
permissions:
  contents: read
  id-token: write

jobs:
  deploy:
    uses: matt-riley/matt-riley-ci/.github/workflows/cloudflare-pages-deploy.yml@v3
    with:
      project-name: my-pages-project
      deploy-directory: dist
      node-version: "22"
      package-manager: pnpm
      pnpm-version: ""
      working-directory: .
      runner: ubuntu-latest
      timeout-minutes: 15
      oidc-audience: ""
    secrets:
      CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
```

**Breaking in v3.** The job now requests `id-token: write`, and a reusable workflow cannot hold a permission its caller has not granted — so every caller must add the `permissions` block above, including callers that keep using the API token. Callers pinned to `@v1` or `@v2` are unaffected until they bump.

`CLOUDFLARE_API_TOKEN` is now optional. Omit it and the workflow exchanges the runner's GitHub OIDC token for a short-lived Cloudflare API token, so no long-lived token is stored:

```yaml
    secrets:
      CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
```

Pass it and that value is used unchanged, which lets a repository migrate on its own schedule. To use OIDC, create a Cloudflare API token with a Gateway condition on the `sub` claim matching the calling repository (for example `repo:matt-riley/my-app`). `oidc-audience` defaults to `https://github.com/<owner>`; set it if the Cloudflare token expects a different audience.

`CLOUDFLARE_ACCOUNT_ID` stays required — OIDC replaces the credential, not the account selector.

### Request Infra Deploy

Dispatches `deploy-app` to the infra repository so the centralized infra workflow can build and deploy the app.

```yaml
jobs:
  request-deploy:
    uses: matt-riley/matt-riley-ci/.github/workflows/request-infra-deploy.yml@v2
    with:
      app-name: my-app
      infra-repo: infra
    secrets:
      PRIVATE_KEY: ${{ secrets.PRIVATE_KEY }}
```

The caller repository must define repository variable `APP_ID` and secret `PRIVATE_KEY`. By default, `infra-repo: infra` targets `${{ github.repository_owner }}/infra`; pass `owner/repo` to target a different infra repository explicitly.

For an immutable artifact deployment, make the caller wait for its artifact job and pass all three artifact fields:

```yaml
jobs:
  request-deploy:
    needs: build
    uses: matt-riley/matt-riley-ci/.github/workflows/request-infra-deploy.yml@v2
    with:
      app-name: my-app
      infra-repo: infra
      artifact-run-id: ${{ github.run_id }}
      artifact-name: my-app-linux-amd64
      artifact-digest: ${{ needs.build.outputs.artifact_digest }}
    secrets:
      PRIVATE_KEY: ${{ secrets.PRIVATE_KEY }}
```

Artifact mode requires `artifact-run-id`, `artifact-name`, and `artifact-digest` together. Existing callers may omit all three fields for source-only dispatches. The GitHub App used by the infra repository must have Actions read access to the source repository so infra can download the exact artifact.

### Tailscale ACL

Validates a tailnet policy file and runs the policy's own ACL tests on pull requests, then applies it on merge to the default branch.

```yaml
permissions:
  contents: read
  id-token: write

jobs:
  acl:
    uses: matt-riley/matt-riley-ci/.github/workflows/tailscale-acl.yml@v2
    with:
      oauth-client-id: ${{ vars.TS_OAUTH_CLIENT_ID }}
      audience: ${{ vars.TS_AUDIENCE }}
      tailnet: "-"
      policy-file: policy.hujson
      action: ""
      runner: ubuntu-latest
      timeout-minutes: 10
      cancel-in-progress: false
      concurrency-suffix: ""
```

This workflow takes **no secrets**. Authentication is [workload identity federation][ts-wif]: the runner mints a short-lived OIDC token and Tailscale exchanges it for a short-lived API token, so nothing long-lived is stored. The client ID and audience are not sensitive, which is why they are inputs rather than secrets — pass them as repository variables. The caller must grant `id-token: write`.

Create the federated identity in the Tailscale admin console with issuer `https://token.actions.githubusercontent.com` and a subject restricted to the calling repository, for example `repo:matt-riley/infra:*`. The audience is `api.tailscale.com/<client id>`.

Leave `action` empty to test on pull requests and apply on pushes to the default branch. Set it to `test` or `apply` to force one — `test` is the right choice when something else, such as Terraform, is the applier, since two owners of the same policy will overwrite each other.

Policy files contain user and group identifiers, so the calling repository should be private.

[ts-wif]: https://tailscale.com/docs/features/workload-identity-federation

### Neovim Format

Runs StyLua with a pinned release.

```yaml
jobs:
  format:
    uses: matt-riley/matt-riley-ci/.github/workflows/nvim-format.yml@v1
    with:
      paths: "lua/ plugin/ tests/"
      runner: ubuntu-latest
      stylua-version: v2.4.0
      timeout-minutes: 15
      cancel-in-progress: false
```

### Neovim Lint

```yaml
jobs:
  lint:
    uses: matt-riley/matt-riley-ci/.github/workflows/nvim-lint.yml@v1
    with:
      paths: "lua/ plugin/ tests/"
      runner: ubuntu-latest
      timeout-minutes: 15
      cancel-in-progress: false
```

### Neovim Tests

Runs plugin tests with a pinned `mini.nvim` checkout.

```yaml
jobs:
  test:
    uses: matt-riley/matt-riley-ci/.github/workflows/nvim-tests.yml@v1
    with:
      neovim-version: neovim
      mini-version: v0.17.0
      runner: ubuntu-latest
      timeout-minutes: 15
      cancel-in-progress: false
```

### Release Please

```yaml
jobs:
  release:
    uses: matt-riley/matt-riley-ci/.github/workflows/release-please.yml@v1
    with:
      runner: ubuntu-latest
      config-file: release-please-config.json
      manifest-file: .release-please-manifest.json
      component-output-key: clients/typescript
      cancel-in-progress: true
    secrets:
      token: ${{ secrets.GITHUB_TOKEN }}
```

Outputs from `release-please.yml`:
- `release_created`
- `tag_name`
- `component_release_created` (for `component-output-key`)
- `component_tag_name` (for `component-output-key`)
- `raw_outputs_json` (full release-please output map)

Example of chaining on release outputs:

```yaml
jobs:
  release:
    uses: matt-riley/matt-riley-ci/.github/workflows/release-please.yml@v1
    with:
      config-file: release-please-config.json
      manifest-file: .release-please-manifest.json
    secrets:
      token: ${{ secrets.GITHUB_TOKEN }}

  publish:
    needs: release
    if: needs.release.outputs.release_created == 'true'
    runs-on: ubuntu-latest
    steps:
      - run: echo "Publishing for tag ${{ needs.release.outputs.tag_name }}"
```

### Go GoReleaser

Runs [GoReleaser](https://goreleaser.com) on tag push. Requires a `.goreleaser.yml` in the repository.

```yaml
jobs:
  release:
    uses: matt-riley/matt-riley-ci/.github/workflows/go-goreleaser.yml@v1
    with:
      runner: ubuntu-latest
      go-version-file: go.mod
      goreleaser-version: "~> v2"
      args: release --clean
      working-directory: .
      timeout-minutes: 30
    secrets:
      github-token: ${{ secrets.GITHUB_TOKEN }}
      homebrew-tap-token: ${{ secrets.HOMEBREW_TAP_GITHUB_TOKEN }}
```

> `github-token` is optional and falls back to `github.token`. Only set `homebrew-tap-token` if GoReleaser publishes to a Homebrew tap.

### Homebrew Formula

Publishes a formula update to a Homebrew tap from four existing release archives.
This is useful for non-GoReleaser projects that already publish archives for
macOS and Linux.

```yaml
jobs:
  homebrew:
    uses: matt-riley/matt-riley-ci/.github/workflows/homebrew-formula.yml@v2
    with:
      tag: v1.2.3
      tap-repo: matt-riley/homebrew-tools
      formula-name: mytool
      class-name: Mytool
      desc: My command line tool
      homepage: https://github.com/matt-riley/mytool
      license: MIT
      binary: mytool
      archive-x86_64-macos: mytool-x86_64-macos.tar.gz
      archive-aarch64-macos: mytool-aarch64-macos.tar.gz
      archive-x86_64-linux: mytool-x86_64-linux.tar.gz
      archive-aarch64-linux: mytool-aarch64-linux.tar.gz
    secrets:
      github-token: ${{ secrets.GITHUB_TOKEN }}
      homebrew-tap-token: ${{ secrets.HOMEBREW_TAP_GITHUB_TOKEN }}
```

`source-repo` defaults to the caller repository. The workflow downloads the
named archives from the release tag, calculates SHA256 checksums, writes
`Formula/<formula-name>.rb`, and pushes only when the formula changes. Missing
`homebrew-tap-token` is a warning by default; set `fail-if-missing-token: true`
to fail the job instead.

### Go Security

Runs [`govulncheck`](https://pkg.go.dev/golang.org/x/vuln/cmd/govulncheck) to detect known vulnerabilities in Go dependencies. Suitable as a PR check or scheduled weekly scan.

```yaml
jobs:
  security:
    uses: matt-riley/matt-riley-ci/.github/workflows/go-security.yml@v1
    with:
      runner: ubuntu-latest
      go-version-file: go.mod
      working-directory: .
      govulncheck-version: v1.1.4
      timeout-minutes: 15
      cancel-in-progress: false
```

### Docker GHCR Publish

```yaml
jobs:
  docker:
    uses: matt-riley/matt-riley-ci/.github/workflows/docker-ghcr-publish.yml@v1
    with:
      runner: ubuntu-latest
      context: .
      dockerfile: ""
      image-name: ghcr.io/owner/repo
      tag-name: v1.2.3
      build-args: ""
      metadata-tags: ""
      metadata-flavor: ""
      platforms: linux/amd64,linux/arm64
      checkout-fetch-depth: 1
      push: true
      provenance: false
      sbom: false
      cancel-in-progress: false
      timeout-minutes: 30
    secrets:
      token: ${{ secrets.GITHUB_TOKEN }}
```

> **Note:** `token` is required and must have `packages:write` permission. The default timeout is 30 minutes (vs 15 minutes for other workflows).

- `tag-name` set: publishes raw semver, `major.minor`, `major`, and `latest` tags.
- `tag-name` empty: publishes short SHA tag only.
- `metadata-tags` set: overrides default tag rules (use for custom tag mapping).
- Outputs:
  - `image_name`
  - `tags`
  - `labels`
  - `digest`

### PNPM Lockfile Sync

```yaml
jobs:
  sync:
    if: startsWith(github.head_ref, 'release-please--')
    uses: matt-riley/matt-riley-ci/.github/workflows/pnpm-lockfile-sync.yml@v1
    with:
      runner: ubuntu-latest
      working-directory: services/webclient
      node-version: "24"
      pnpm-version: "10"
      lockfile-name: pnpm-lock.yaml
      install-command: pnpm install --no-frozen-lockfile --lockfile-only
      commit-message: chore(webclient): sync pnpm lockfile
      cancel-in-progress: false
      timeout-minutes: 15
    secrets:
      token: ${{ secrets.RELEASE_PLEASE_TOKEN }}
```

See the Release Please outputs above when chaining on `release_created` or `tag_name` in `if` conditions.

## Token guidance for release-please

- Start with `GITHUB_TOKEN` in most repositories.
- Use a PAT only when branch protections or org policies block PR/release automation with `GITHUB_TOKEN`.

## Repository self-validation

- This repository includes `.github/workflows/validate-workflows.yml` to validate workflow YAML and enforce SHA-pinned actions.
- This repository includes `.github/workflows/contract-tests.yml` to run smoke tests against the reusable workflows.
- This repository includes `.github/workflows/repository-release-please.yml` plus `release-please-config.json` and `.release-please-manifest.json` to version the workflow library from `main`.
- This repository includes `.github/workflows/monthly-docs-audit.md` (compiled to `.lock.yml`) to run a monthly agentic documentation audit and publish a findings report issue.

## Version governance

- Publish non-breaking updates as `v1.x.y`.
- Move the floating `v1` tag to the latest compatible `v1.x.y` release after validation.
- Introduce `v2` only for intentionally breaking input/behavior changes.
