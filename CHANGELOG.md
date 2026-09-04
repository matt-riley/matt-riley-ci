# Changelog

## [3.1.0](https://github.com/matt-riley/matt-riley-ci/compare/v3.0.1...v3.1.0) (2026-09-04)


### Features

* mint homebrew tap token from GitHub App in goreleaser workflow ([6cc4949](https://github.com/matt-riley/matt-riley-ci/commit/6cc4949c39c22de22cc65f70305e2344416c3f50))


### Bug Fixes

* accept expression values for artifact-run-id input ([#104](https://github.com/matt-riley/matt-riley-ci/issues/104)) ([3a7b18f](https://github.com/matt-riley/matt-riley-ci/commit/3a7b18fc7be1a2b7ee2de806f2c631ca661ea6a9))
* use permission-contents input for create-github-app-token ([2b0008a](https://github.com/matt-riley/matt-riley-ci/commit/2b0008a45ef931f133d0e6af65541d0292e56d82))

## [3.0.1](https://github.com/matt-riley/matt-riley-ci/compare/v3.0.0...v3.0.1) (2026-07-31)


### Bug Fixes

* publish the floating major tag with a token that can ([#100](https://github.com/matt-riley/matt-riley-ci/issues/100)) ([495110b](https://github.com/matt-riley/matt-riley-ci/commit/495110bf7b565a1a97d4f1618901b3c839c79693))

## [3.0.0](https://github.com/matt-riley/matt-riley-ci/compare/v2.4.1...v3.0.0) (2026-07-29)


### ⚠ BREAKING CHANGES

* the deploy job requests `id-token: write`, and a reusable workflow cannot hold a permission its caller has not granted. Every caller must add `permissions: id-token: write`, including callers that keep passing CLOUDFLARE_API_TOKEN. Callers pinned to `@v1` or `@v2` are unaffected until they bump.

### Features

* add tailscale-acl reusable workflow ([#97](https://github.com/matt-riley/matt-riley-ci/issues/97)) ([cb8687d](https://github.com/matt-riley/matt-riley-ci/commit/cb8687d378f5bca6f14c4f8450f0f437b8146314))
* authenticate Cloudflare Pages deploys by OIDC ([#98](https://github.com/matt-riley/matt-riley-ci/issues/98)) ([5cb8c0d](https://github.com/matt-riley/matt-riley-ci/commit/5cb8c0d9ccc5e79c3ef18514ef958aa457de6e0c))


### Bug Fixes

* refresh Go caches from trusted main runs ([#95](https://github.com/matt-riley/matt-riley-ci/issues/95)) ([be15491](https://github.com/matt-riley/matt-riley-ci/commit/be1549198ac2b0582dd19d0da8ef7872c2fb653b))

## [2.4.1](https://github.com/matt-riley/matt-riley-ci/compare/v2.4.0...v2.4.1) (2026-07-18)


### Bug Fixes

* release immutable infra artifact handoff ([#91](https://github.com/matt-riley/matt-riley-ci/issues/91)) ([328c7bd](https://github.com/matt-riley/matt-riley-ci/commit/328c7bd30116938c846b1cfc3188914e0dd3c5cb))

## [2.4.0](https://github.com/matt-riley/matt-riley-ci/compare/v2.3.0...v2.4.0) (2026-07-18)


### Features

* Codex/waffle hetzner deployment ([#89](https://github.com/matt-riley/matt-riley-ci/issues/89)) ([9b99d0a](https://github.com/matt-riley/matt-riley-ci/commit/9b99d0a091d105cad7ed5728373225e143efd2f4))
* pass immutable artifacts to infra deploys ([3d73ebe](https://github.com/matt-riley/matt-riley-ci/commit/3d73ebeba8b7226fc445cd87e4f9a74a8f088f2c))

## [2.3.0](https://github.com/matt-riley/matt-riley-ci/compare/v2.2.0...v2.3.0) (2026-07-03)


### Features

* restore go-ci.yml workflow with cache fix ([#80](https://github.com/matt-riley/matt-riley-ci/issues/80)) ([071c2c2](https://github.com/matt-riley/matt-riley-ci/commit/071c2c2bbe410f73126d3cefd0a0b6812b3565f6))

## [2.2.0](https://github.com/matt-riley/matt-riley-ci/compare/v2.1.0...v2.2.0) (2026-07-01)


### Features

* restore go-ci.yml workflow with cache fix ([#80](https://github.com/matt-riley/matt-riley-ci/issues/80)) ([071c2c2](https://github.com/matt-riley/matt-riley-ci/commit/071c2c2bbe410f73126d3cefd0a0b6812b3565f6))


### Bug Fixes

* add cache-dependency-path for mono-repo go.mod support ([#78](https://github.com/matt-riley/matt-riley-ci/issues/78)) ([69072da](https://github.com/matt-riley/matt-riley-ci/commit/69072da4c9ad3988635b47728b64c30e593da027))

## [2.1.0](https://github.com/matt-riley/matt-riley-ci/compare/v2.0.0...v2.1.0) (2026-06-26)


### Features

* add reusable homebrew formula workflow ([9558d9e](https://github.com/matt-riley/matt-riley-ci/commit/9558d9e0b4cf7ce0bd0786f7300f2aae0eab0683))
* **ci:** cache pnpm, npm, Go, and Playwright artefacts ([#71](https://github.com/matt-riley/matt-riley-ci/issues/71)) ([b15b931](https://github.com/matt-riley/matt-riley-ci/commit/b15b931fc63a0bd86402c5276aeb360770180a65))

## [2.0.0](https://github.com/matt-riley/matt-riley-ci/compare/v1.10.0...v2.0.0) (2026-06-12)


### ⚠ BREAKING CHANGES

* Replace language-specific workflows (go-ci.yml, node-ci.yml, bun-ci.yml) with single ci.yml that uses mise tasks.

### Features

* **ci:** make universal workflow run standard mise tasks ([8ba289b](https://github.com/matt-riley/matt-riley-ci/commit/8ba289b7e39c9e16aa6435f10b2e7a68b8bbde84))


### Code Refactoring

* consolidate to single universal ci.yml workflow ([b9b45e8](https://github.com/matt-riley/matt-riley-ci/commit/b9b45e86385390dacd1c7a607a35719b1dc41dcd))
