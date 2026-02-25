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
      go-version-file: go.mod
      working-directory: .
      run-race: false
      run-vet: true
      timeout-minutes: 15
      test-args: ""
```

### Node CI

```yaml
jobs:
  ci:
    uses: matt-riley/matt-riley-ci/.github/workflows/node-ci.yml@v1
    with:
      node-version: "22"
      package-manager: pnpm
      working-directory: .
      cache-dependency-path: pnpm-lock.yaml
      run-lint: true
      run-test: true
      run-build: false
```

### Bun CI

```yaml
jobs:
  ci:
    uses: matt-riley/matt-riley-ci/.github/workflows/bun-ci.yml@v1
    with:
      bun-version: latest
      working-directory: .
      run-test: true
```

### Release Please

```yaml
jobs:
  release:
    uses: matt-riley/matt-riley-ci/.github/workflows/release-please.yml@v1
    with:
      config-file: release-please-config.json
      manifest-file: .release-please-manifest.json
    secrets:
      token: ${{ secrets.GITHUB_TOKEN }}
```

Outputs from `release-please.yml`:
- `release_created`
- `tag_name`
