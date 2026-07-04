# Changelog

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
