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
      run-race: false
      run-vet: true
      run-fmt: false
      timeout-minutes: 15
      test-args: ""
      cancel-in-progress: false
```

### Go Lint

```yaml
jobs:
  lint:
    uses: matt-riley/matt-riley-ci/.github/workflows/go-lint.yml@v1
    with:
      runner: ubuntu-latest
      go-version-file: go.mod
      working-directory: .
      golangci-version: v2.2.0
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
      cache-dependency-path: pnpm-lock.yaml
      require-lockfile: false
      install-command: ""
      run-lint: true
      run-test: true
      run-build: false
      test-script: test
      verify-lockfile-clean: false
      lockfile-path: ""
      build-env: ""
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
      run-test: true
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
      govulncheck-version: latest
      timeout-minutes: 15
      cancel-in-progress: false
```

### Release Please Guard

Repairs stale merged release PRs that still carry the `autorelease: pending` label — a known edge case in `release-please`. Run on a schedule alongside the standard `release-please.yml` workflow.

```yaml
on:
  schedule:
    - cron: "17 * * * *"
  workflow_dispatch:

jobs:
  guard:
    uses: matt-riley/matt-riley-ci/.github/workflows/release-please-guard.yml@v1
    with:
      main-branch: main
      release-please-workflow: release-please.yml
```

> Tag naming convention: the root component `"."` maps to `v{version}`; any other path maps to `{basename}-v{version}` (e.g. `clients/typescript` → `typescript-client-v1.2.3` is **not** assumed — use the basename convention `typescript-v1.2.3` instead). Adjust your `.goreleaser.yml` tag config to match.

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
      metadata-tags: ""
      metadata-flavor: ""
      platforms: linux/amd64,linux/arm64
      push: true
      cancel-in-progress: false
      timeout-minutes: 30
    secrets:
      token: ${{ secrets.GITHUB_TOKEN }}
```

> **Note:** `token` is required and must have `packages:write` permission. The default timeout is 30 minutes (vs 15 minutes for other workflows).

- `tag-name` set: publishes raw semver, `major.minor`, `major`, and `latest` tags.
- `tag-name` empty: publishes short SHA tag only.
- `metadata-tags` set: overrides default tag rules (use for custom tag mapping).

### PNPM Lockfile Sync

```yaml
jobs:
  sync:
    if: startsWith(github.head_ref, 'release-please--')
    uses: matt-riley/matt-riley-ci/.github/workflows/pnpm-lockfile-sync.yml@v1
    with:
      working-directory: services/webclient
      node-version: "24"
      pnpm-version: "10"
      lockfile-name: pnpm-lock.yaml
      install-command: pnpm install --no-frozen-lockfile --lockfile-only
      commit-message: chore(webclient): sync pnpm lockfile
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
