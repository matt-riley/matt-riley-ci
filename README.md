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
      working-directory: .
      cache-dependency-path: pnpm-lock.yaml
      require-lockfile: false
      run-lint: true
      run-test: true
      run-build: false
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
      cancel-in-progress: true
    secrets:
      token: ${{ secrets.GITHUB_TOKEN }}
```

Outputs from `release-please.yml`:
- `release_created`
- `tag_name`

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

## Version governance

- Publish non-breaking updates as `v1.x.y`.
- Move the floating `v1` tag to the latest compatible `v1.x.y` release after validation.
- Introduce `v2` only for intentionally breaking input/behavior changes.
