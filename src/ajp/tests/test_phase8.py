import unittest
import os
import yaml
import json
import re
import sys
if sys.version_info >= (3, 11):
    import tomllib as toml
else:
    try:
        import toml
    except ImportError:
        import json as toml  # fallback

SKILLS_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestCIPipeline(unittest.TestCase):
    """Test CI/CD pipeline configuration."""

    def test_ci_workflow_exists(self):
        ci_path = os.path.join(SKILLS_DIR, ".github", "workflows", "ci.yml")
        self.assertTrue(os.path.exists(ci_path), "CI workflow file missing")

    def test_release_workflow_exists(self):
        release_path = os.path.join(SKILLS_DIR, ".github", "workflows", "release.yml")
        self.assertTrue(os.path.exists(release_path), "Release workflow file missing")

    def test_ci_workflow_structure(self):
        ci_path = os.path.join(SKILLS_DIR, ".github", "workflows", "ci.yml")
        with open(ci_path) as f:
            workflow = yaml.safe_load(f)

        self.assertIn("name", workflow)
        self.assertIn("on", workflow)
        self.assertIn("jobs", workflow)

        jobs = workflow["jobs"]
        self.assertIn("lint", jobs)
        self.assertIn("test", jobs)
        self.assertIn("security", jobs)
        self.assertIn("build", jobs)
        self.assertIn("integration", jobs)

    def test_ci_test_matrix(self):
        ci_path = os.path.join(SKILLS_DIR, ".github", "workflows", "ci.yml")
        with open(ci_path) as f:
            workflow = yaml.safe_load(f)

        test_job = workflow["jobs"]["test"]
        strategy = test_job["strategy"]
        matrix = strategy["matrix"]
        python_versions = matrix["python"]

        self.assertIn("3.9", python_versions)
        self.assertIn("3.11", python_versions)
        self.assertIn("3.12", python_versions)

    def test_ci_security_scan(self):
        ci_path = os.path.join(SKILLS_DIR, ".github", "workflows", "ci.yml")
        with open(ci_path) as f:
            workflow = yaml.safe_load(f)

        security_job = workflow["jobs"]["security"]
        steps = security_job["steps"]
        step_commands = [s.get("run", "") for s in steps if "run" in s]
        all_commands = " ".join(step_commands)

        self.assertIn("bandit", all_commands)
        self.assertIn("safety", all_commands)

    def test_ci_integration_postgres(self):
        ci_path = os.path.join(SKILLS_DIR, ".github", "workflows", "ci.yml")
        with open(ci_path) as f:
            workflow = yaml.safe_load(f)

        integration = workflow["jobs"]["integration"]
        self.assertIn("services", integration)
        self.assertIn("postgres", integration["services"])

    def test_release_workflow_structure(self):
        release_path = os.path.join(SKILLS_DIR, ".github", "workflows", "release.yml")
        with open(release_path) as f:
            workflow = yaml.safe_load(f)

        self.assertIn("on", workflow)
        on_config = workflow["on"]
        self.assertIn("push", on_config)
        self.assertIn("tags", on_config["push"])

        jobs = workflow["jobs"]
        self.assertIn("publish", jobs)

    def test_release_publish_to_pypi(self):
        release_path = os.path.join(SKILLS_DIR, ".github", "workflows", "release.yml")
        with open(release_path) as f:
            workflow = yaml.safe_load(f)

        publish_job = workflow["jobs"]["publish"]
        self.assertIn("permissions", publish_job)
        self.assertEqual(publish_job["permissions"]["id-token"], "write")


class TestDockerConfig(unittest.TestCase):
    """Test Docker configuration files."""

    def test_dockerfile_exists(self):
        dockerfile_path = os.path.join(SKILLS_DIR, "Dockerfile")
        self.assertTrue(os.path.exists(dockerfile_path), "Dockerfile missing")

    def test_dockerfile_multistage(self):
        dockerfile_path = os.path.join(SKILLS_DIR, "Dockerfile")
        with open(dockerfile_path) as f:
            content = f.read()

        self.assertIn("AS builder", content)
        self.assertIn("FROM python:3.11-slim", content)
        self.assertIn("USER ajp", content)
        self.assertIn("EXPOSE 8000", content)

    def test_docker_compose_exists(self):
        compose_path = os.path.join(SKILLS_DIR, "docker-compose.yml")
        self.assertTrue(os.path.exists(compose_path), "docker-compose.yml missing")

    def test_docker_compose_services(self):
        compose_path = os.path.join(SKILLS_DIR, "docker-compose.yml")
        with open(compose_path) as f:
            compose = yaml.safe_load(f)

        services = compose["services"]
        self.assertIn("ajp-server", services)
        self.assertIn("postgres", services)
        self.assertIn("vault", services)
        self.assertIn("otel-collector", services)

    def test_docker_compose_postgres_config(self):
        compose_path = os.path.join(SKILLS_DIR, "docker-compose.yml")
        with open(compose_path) as f:
            compose = yaml.safe_load(f)

        postgres = compose["services"]["postgres"]
        self.assertIn("image", postgres)
        self.assertIn("environment", postgres)
        self.assertIn("healthcheck", postgres)

    def test_docker_compose_healthchecks(self):
        compose_path = os.path.join(SKILLS_DIR, "docker-compose.yml")
        with open(compose_path) as f:
            compose = yaml.safe_load(f)

        server = compose["services"]["ajp-server"]
        self.assertIn("healthcheck", server)


class TestMakefile(unittest.TestCase):
    """Test Makefile targets."""

    def test_makefile_exists(self):
        makefile_path = os.path.join(SKILLS_DIR, "Makefile")
        self.assertTrue(os.path.exists(makefile_path), "Makefile missing")

    def test_makefile_targets(self):
        makefile_path = os.path.join(SKILLS_DIR, "Makefile")
        with open(makefile_path) as f:
            content = f.read()

        targets = ["install", "test", "lint", "security", "build", "docker-up", "server"]
        for target in targets:
            self.assertIn(target + ":", content, f"Makefile missing target: {target}")


class TestPreCommit(unittest.TestCase):
    """Test pre-commit configuration."""

    def test_precommit_config_exists(self):
        config_path = os.path.join(SKILLS_DIR, ".pre-commit-config.yaml")
        self.assertTrue(os.path.exists(config_path), "Pre-commit config missing")

    def test_precommit_hooks(self):
        config_path = os.path.join(SKILLS_DIR, ".pre-commit-config.yaml")
        with open(config_path) as f:
            config = yaml.safe_load(f)

        repos = [r["repo"] for r in config["repos"]]
        self.assertTrue(any("ruff" in r for r in repos), "Ruff hook missing")
        self.assertTrue(any("mypy" in r for r in repos), "Mypy hook missing")


class TestPyproject(unittest.TestCase):
    """Test pyproject.toml configuration."""

    def test_pyproject_exists(self):
        pyproject_path = os.path.join(SKILLS_DIR, "pyproject.toml")
        self.assertTrue(os.path.exists(pyproject_path), "pyproject.toml missing")

    def test_pyproject_metadata(self):
        pyproject_path = os.path.join(SKILLS_DIR, "pyproject.toml")
        with open(pyproject_path, "rb") as f:
            config = toml.load(f)

        project = config["project"]
        self.assertEqual(project["name"], "ajp-agent-journal-protocol")
        self.assertEqual(project["requires-python"], ">=3.9")

    def test_pyproject_optional_deps(self):
        pyproject_path = os.path.join(SKILLS_DIR, "pyproject.toml")
        with open(pyproject_path, "rb") as f:
            config = toml.load(f)

        optional = config["project"]["optional-dependencies"]
        expected = ["dev", "server", "sdk", "postgres", "vault", "temporal", "opentelemetry", "all"]
        for dep_group in expected:
            self.assertIn(dep_group, optional, f"Missing optional dep group: {dep_group}")

    def test_pyproject_tool_configs(self):
        pyproject_path = os.path.join(SKILLS_DIR, "pyproject.toml")
        with open(pyproject_path, "rb") as f:
            config = toml.load(f)

        tools = config["tool"]
        self.assertIn("ruff", tools)
        self.assertIn("mypy", tools)
        self.assertIn("pytest", tools)


class TestOtelConfig(unittest.TestCase):
    """Test OpenTelemetry collector configuration."""

    def test_otel_config_exists(self):
        otel_path = os.path.join(SKILLS_DIR, "otel-config.yaml")
        self.assertTrue(os.path.exists(otel_path), "OTel config missing")

    def test_otel_config_structure(self):
        otel_path = os.path.join(SKILLS_DIR, "otel-config.yaml")
        with open(otel_path) as f:
            config = yaml.safe_load(f)

        self.assertIn("receivers", config)
        self.assertIn("processors", config)
        self.assertIn("exporters", config)
        self.assertIn("service", config)

        pipelines = config["service"]["pipelines"]
        self.assertIn("traces", pipelines)
        self.assertIn("metrics", pipelines)
        self.assertIn("logs", pipelines)


if __name__ == "__main__":
    unittest.main()
