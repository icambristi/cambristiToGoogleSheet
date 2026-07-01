# Changelog

All notable changes to this project will be documented in this file.

## [0.1.4] - 2026-07-01

### Added
- Full pytest suite for `writeGoogleSheet.py` (76 tests, 99% line coverage)
- CI: Trivy vulnerability scan gates the Docker build — fails on CRITICAL/HIGH CVEs before the image is pushed to Docker Hub
- Dependabot config for weekly updates to the Docker base image, Python deps, and GitHub Actions versions
- GitHub secret scanning and push protection enabled (repo is now public)

### Fixed
- `upd_members_db_to_google_sheet`: comparing a tz-aware `datetime.now(UTC)` against tz-naive parsed `cotisationExpiration` raised `TypeError` whenever geomap ran on expiration strings without a UTC offset

### Removed
- `build.sh` untracked from git (kept local-only) — redundant with CI and leaked the deploy server's SSH host alias/port

## [0.1.3] - 2026-06-30

### Changed
- Activity filtering: summary sheet and per-activity worksheets now only include activities from current year onward
- Logging: removed unused remote logging config block
- Logging: `send_log_request` now uses `logging.exception()` to capture full tracebacks

## [0.1.2] - 2026-06

### Changed
- Refactored `writeGoogleSheet.py` column definitions and formatting
- Added `membreEffectif` field to members sheet
- Optimized Docker build process; enforced Node.js version in Docker workflow

## [0.1.1] - 2026-05

### Added
- `upd_logs_google_sheet` refactored for better modularity and error handling
- Linting and type-checking dependencies added to `pyproject.toml` (`ruff`, `pyright`, `mypy`)

### Changed
- Simplified function signatures in `writeGoogleSheet.py`
- Centralized musician formatting logic into `fmt_musicians`
- Streamlined participant data handling

### Removed
- `old_writeGoogleSheet.py`
- `queryLog.py`

## [0.1.0] - 2026-04

### Added
- Initial Docker deployment workflow with SSH remote action
- Google Sheets sync for members, plans, activities, and logs
- Geolocation map generation via TomTom API
- InfluxDB integration for log retrieval
