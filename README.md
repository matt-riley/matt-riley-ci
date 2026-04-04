# matt-riley-ci

Reusable GitHub Actions workflows for Matt Riley repositories.

## Versioning

- Use `@v1` for non-breaking updates on the major line.
- Use `@v1.x.y` for fully pinned workflow behavior.
- Breaking changes are released under a new major tag (for example `@v2`).

## Workflows

### Go CI

```yaml
jobs:
  ci:
    uses: matt-riley/matt-riley-ci/.github/workflows/go-ci.yml@v1
    with:
      runner: ubuntu-latest
      go-version-file: go.mod
      working-directory: .
      run-test: true
      run-race: false
      run-vet: true
      run-fmt: false
      test-args: ""
      test-command: ""
      build-command: ""
      coverage-path: ""
      coverage-artifact-name: ""
      timeout-minutes: 15
      cancel-in-progress: false
      concurrency-suffix: ""
```

Set `concurrency-suffix` when invoking this workflow multiple times in the same workflow file to avoid concurrency group collisions between calls.

Use `run-test: false` for build-only or format-only invocations, `build-command` for an explicit build step, `test-command` when the default `go test ./...` contract is not enough, and `coverage-path` + `coverage-artifact-name` to publish coverage output for downstream jobs such as Codecov uploads. When `test-command` is set, the workflow does not apply `test-args` or `run-race` automatically; include any desired extra args or race flags directly in the custom command.

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

### Node CI

```yaml
jobs:
  ci:
    uses: matt-riley/matt-riley-ci/.github/workflows/node-ci.yml@v1
    with:
      node-version: "22"
      runner: ubuntu-latest
      package-manager: pnpm
      pnpm-version: ""
      working-directory: .
      cache-dependency-path: ""
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
```

### Bun CI

```yaml
jobs:
  ci:
    uses: matt-riley/matt-riley-ci/.github/workflows/bun-ci.yml@v1
    with:
      bun-version: latest
      runner: ubuntu-latest
      working-directory: .
      frozen-lockfile: true
      require-lockfile: false
      run-lint: false
      run-test: true
      timeout-minutes: 15
      cancel-in-progress: false
```

### Cloudflare Pages Deploy

Builds a Node-based project and deploys it to Cloudflare Pages.

```yaml
jobs:
  deploy:
    uses: matt-riley/matt-riley-ci/.github/workflows/cloudflare-pages-deploy.yml@v1
    with:
      project-name: my-pages-project
      deploy-directory: dist
      node-version: "22"
      package-manager: pnpm
      pnpm-version: ""
      working-directory: .
      runner: ubuntu-latest
      timeout-minutes: 15
    secrets:
      CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
      CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
```

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

## Token guidance for release-please

- Start with `GITHUB_TOKEN` in most repositories.
- Use a PAT only when branch protections or org policies block PR/release automation with `GITHUB_TOKEN`.

## Repository self-validation

- This repository includes `.github/workflows/validate-workflows.yml` to validate workflow YAML and enforce SHA-pinned actions.
- This repository includes `.github/workflows/contract-tests.yml` to run smoke tests against the reusable workflows.
- This repository includes `.github/workflows/monthly-docs-audit.md` (compiled to `.lock.yml`) to run a monthly agentic documentation audit and publish a findings report issue.

## Version governance

- Publish non-breaking updates as `v1.x.y`.
- Move the floating `v1` tag to the latest compatible `v1.x.y` release after validation.
- Introduce `v2` only for intentionally breaking input/behavior changes.
