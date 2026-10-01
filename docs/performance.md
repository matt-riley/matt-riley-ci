# Performance and task boundaries

Keep CI work proportional to the job. Universal CI installs consumer-declared tools once, then runs one mise task graph with `--skip-tools`. Use `install-tools: node pnpm` to avoid installing unrelated root tools. Missing tools then fail clearly rather than triggering hidden installation. Go adapters use setup-go directly and never install mise. Neovim adapters download small, versioned binary assets rather than invoking apt.

The graph owns dependencies. An install task shared by build and test runs once per mise invocation. Use `task-jobs: 4` when the graph correctly declares dependencies and the independent work benefits from parallelism; the conservative default is one. Avoid running several CPU-heavy jobs in parallel inside a small runner just to increase the count. Keep lint/type checks independent where appropriate and build once before publishing an artifact.

## Browser setup belongs to browser tests

In [mattriley.tools run 36900352656](https://github.com/matt-riley/mattriley.tools/actions/runs/36900352656), mise setup succeeded and installed no new tools: Node and pnpm were restored. The repository's `install` task then invoked `playwright install --with-deps chromium webkit`, in both the CI and generated-data jobs. Each job installed 181 Ubuntu packages, upgraded six, downloaded 125 MB, and used 364 MB of additional disk space. In [run 36848891061](https://github.com/matt-riley/mattriley.tools/actions/runs/36848891061), mise setup took three seconds while the CI install task took forty seconds. Both failures occurred later in `astro check`, which rejected TypeScript 7's missing programmatic API. Replacing the mise action alone would not address either cause.

Separate package installation from browser setup:

```toml
[tasks.install]
run = "pnpm install --frozen-lockfile"

[tasks.browser-setup]
depends = ["install"]
run = "pnpm exec playwright install --with-deps chromium webkit"

[tasks.test-mobile]
depends = ["browser-setup"]
run = "pnpm run test:mobile"

[tasks.generate-data]
depends = ["install"]
run = "pnpm run generate:data"

[tasks.ci]
depends = ["lint", "test", "test-mobile", "build"]
```

Add each package-dependent task's `depends = ["install"]` too. Data generation, linting, and builds should not install browsers. Chromium-only suites should only install Chromium. WebKit's Linux system dependencies are substantial; keep them when WebKit coverage is required. Browser binary caching does not cache apt-installed OS libraries. A pinned Playwright container with the matching package version, or an appropriately provisioned runner, can eliminate repeated OS setup; account for image download time before claiming an improvement. The caller owns the container/runner choice.

Set `playwright-cache: true` only for browser-test jobs. Library workflows never add browser installation implicitly and do not skip necessary system libraries on a cache hit.

## Caches and build outputs

- Universal dependency caches include OS, architecture, project directory, detected tool versions and project lockfiles. Go build caches also include the revision, with compatible fallback keys. Extra cache paths and dependency globs support other ecosystems.
- Cache restores are enabled by default. Writes require `save-cache: true`, successful execution, and a push/manual run on the default branch. Designate one writer per project instead of making every parallel job upload the same cache. PRs read caches without updating trusted branch caches.
- Pinned govulncheck binaries also use OS/architecture/Go/scanner version keys, avoiding repeated compilation after a designated trusted writer populates the cache. Floating scanner versions bypass this binary cache.
- Docker caches use image, context, Dockerfile and platforms as their default namespace. Native single-platform builds skip QEMU. Multi-platform output remains an explicit option. Validation builds do not log in or upload the BuildKit cache.
- Pages deploys download a same-run build artifact and install only Wrangler's runtime. They do not rebuild the application. Use `needs: build` and pass the producer's artifact name.
- Keep artifact retention short (default seven days); choose unique artifact names for matrices. Docker attestations default on for publishing, so account for their cost without dropping provenance to shave a few seconds.

## Measuring honestly

Compare equivalent revisions, runner images and task selections. Measure cold and warm cache runs separately, include artifact/cache transfer time, and inspect the exact slow step. A fast smoke fixture proves the workflow contract, not a speedup for a large application. The local regression suite checks shared dependency execution; hosted consumer timings are recorded in the implementation plan once available.

In [consumer run 36906004644](https://github.com/matt-riley/matt-riley-ci/actions/runs/36906004644), all consumer checks passed: mise setup took five seconds for Node, three for Bun and four for the language-neutral fixture; Neovim setup took two seconds. Docker skipped QEMU on the native build. The scanner's uncached compilation took nineteen seconds, motivating its pinned binary cache. These are small-fixture step timings with runner/cache state specific to that run, not before/after application benchmarks or guarantees.
