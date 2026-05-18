.PHONY: install test lint security build clean docker-up docker-down

install:
	pip install -e ".[dev]"

install-all:
	pip install -e ".[all]"

test:
	pytest src/ajp/tests/ -v --tb=short

test-cov:
	pytest src/ajp/tests/ -v --tb=short --cov=ajp --cov-report=html

lint:
	ruff check src/ajp/
	mypy src/ajp/ --ignore-missing-imports

security:
	bandit -r src/ajp/ -ll
	safety check

build:
	python -m build

clean:
	rm -rf dist/ build/ *.egg-info src/*.egg-info __pycache__ src/__pycache__
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete

docker-up:
	docker compose up -d

docker-down:
	docker compose down

server:
	ajp-server --host 0.0.0.0 --port 8000

release:
	git tag -a "v$${VERSION}" -m "Release v$${VERSION}"
	git push origin "v$${VERSION}"
