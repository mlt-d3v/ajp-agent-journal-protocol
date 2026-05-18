# Phase 8: CI/CD Pipeline Session Notes

## Date: 2025-06-18
## Status: Complete (24 tests, 316 total)

## What Was Built

### GitHub Actions Workflows
- `ci.yml`: Lint (ruff+mypy), test matrix (Python 3.9-3.12), security (bandit+safety), build, integration with PostgreSQL service
- `release.yml`: Tag-triggered PyPI publish with OIDC authentication
- Pre-commit hooks: ruff, ruff-format, mypy, bandit

### Docker Infrastructure
- Multi-stage Dockerfile (builder + runtime, non-root user, port 8000)
- Docker Compose: AJP server, PostgreSQL 16, HashiCorp Vault, OTel Collector, Grafana
- Health checks and service dependencies

### Build & Dev Tooling
- `pyproject.toml`: setuptools, optional deps, tool configs (ruff, mypy, pytest)
- `Makefile`: install, test, test-cov, lint, security, build, docker-up/down, server, release
- `otel-config.yaml`: OTel collector config for traces, metrics, logs pipelines

## Bugs Fixed During Build

1. **YAML `on:` key parses as boolean `True` in PyYAML**
   - PyYAML treats `on:` as `True:` (boolean)
   - Fix: Quote as `"on":` in YAML files when testing with `yaml.safe_load()`
   - Impact: All CI workflow tests failed until this was fixed

2. **`tomllib` (Python 3.11+) requires binary file mode**
   - `tomllib.load()` requires `"rb"` mode, not text mode
   - Fix: Use `open(path, "rb")` for all toml loads
   - Impact: pyproject.toml test assertions failed

3. **SKILLS_DIR path resolution**
   - Test files need 4 `dirname()` levels to reach project root
   - Path: test file -> tests -> ajp -> src -> project root
   - Fix: `os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))`

## Test Results
- 24 Phase 8 tests passing
- 316 total tests across all 8 phases
- All tests pass on Python 3.11

## Key Commands
```bash
# Install with all deps
pip install -e ".[all]"

# Run all tests
pytest src/ajp/tests/ -v --tb=short

# Run with coverage
pytest src/ajp/tests/ -v --tb=short --cov=ajp --cov-report=html

# Lint and type check
ruff check src/ajp/
mypy src/ajp/ --ignore-missing-imports

# Security scan
bandit -r src/ajp/ -ll
safety check

# Build package
python -m build

# Docker stack
docker compose up -d
```

## Files Created
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- `Dockerfile`
- `docker-compose.yml`
- `otel-config.yaml`
- `Makefile`
- `.pre-commit-config.yaml`
- `pyproject.toml` (updated)
- `src/ajp/tests/test_phase8.py`

## Integration Notes
- CI pipeline tests run against mock integrations (no real PostgreSQL/Vault needed)
- Integration tests use PostgreSQL service container in GitHub Actions
- Release workflow uses PyPI trusted publishing (OIDC)
- Docker Compose provides full local development environment
