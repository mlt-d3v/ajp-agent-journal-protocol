"""Phase 7: Real Integrations Tests - PostgreSQL, Vault, Temporal, OpenTelemetry."""
import asyncio
import unittest
import time
import json
from unittest.mock import patch, AsyncMock, MagicMock

# Test PostgreSQL integration
from ajp.integrations.postgres import PostgresStorage, PostgresConfig, PostgresLogLevel

# Test Vault integration
from ajp.integrations.vault import RealVaultClient, VaultConfig, VaultAuthConfig, VaultAuthMethod

# Test Temporal integration
from ajp.integrations.temporal import (
    TemporalWorkflowEngine, WorkflowConfig, WorkflowType, WorkflowStatus, WorkflowExecution
)

# Test OpenTelemetry integration
from ajp.integrations.opentelemetry import (
    OTLPExporter, OTelConfig, SpanKind, SpanStatus, MetricType
)


class TestPostgresConfig(unittest.TestCase):
    """Test PostgreSQL configuration."""

    def test_default_config(self):
        config = PostgresConfig()
        self.assertEqual(config.host, "localhost")
        self.assertEqual(config.port, 5432)
        self.assertEqual(config.database, "ajp_journal")
        self.assertEqual(config.pool_size, 10)

    def test_dsn_generation(self):
        config = PostgresConfig(host="prod.db.com", user="admin", password="secret")
        dsn = config.get_dsn()
        self.assertIn("prod.db.com", dsn)
        self.assertIn("admin", dsn)
        self.assertIn("secret", dsn)

    def test_ssl_dsn(self):
        config = PostgresConfig(ssl_enabled=True)
        dsn = config.get_dsn()
        self.assertIn("sslmode=require", dsn)

    def test_to_dict(self):
        config = PostgresConfig()
        d = config.to_dict()
        self.assertIsInstance(d, dict)
        self.assertIn("host", d)
        self.assertIn("port", d)

    def test_custom_config(self):
        config = PostgresConfig(
            host="custom.host",
            port=5433,
            database="custom_db",
            pool_size=20,
            log_level=PostgresLogLevel.DEBUG,
        )
        self.assertEqual(config.host, "custom.host")
        self.assertEqual(config.port, 5433)
        self.assertEqual(config.log_level, PostgresLogLevel.DEBUG)


class TestPostgresStorage(unittest.TestCase):
    """Test PostgreSQL storage backend."""

    def test_initialization(self):
        storage = PostgresStorage()
        self.assertFalse(storage.is_connected)
        self.assertEqual(storage.write_count, 0)
        self.assertEqual(storage.read_count, 0)

    def test_connect_without_asyncpg(self):
        storage = PostgresStorage()
        # Without asyncpg installed, connect should return False gracefully
        result = asyncio.get_event_loop().run_until_complete(storage.connect())
        self.assertFalse(result)
        self.assertFalse(storage.is_connected)

    def test_write_without_connection(self):
        storage = PostgresStorage()

        async def test():
            result = await storage.write_entry({"entry_id": "test"})
            return result

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertFalse(result)

    def test_read_without_connection(self):
        storage = PostgresStorage()

        async def test():
            result = await storage.read_entries()
            return result

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertEqual(result, [])

    def test_delete_without_connection(self):
        storage = PostgresStorage()

        async def test():
            result = await storage.delete_entries("agent-1")
            return result

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertEqual(result, 0)

    def test_stats_without_connection(self):
        storage = PostgresStorage()

        async def test():
            result = await storage.get_stats()
            return result

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertEqual(result["connected"], False)

    def test_close_without_connection(self):
        storage = PostgresStorage()

        async def test():
            await storage.close()
            return True

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertTrue(result)

    def test_write_entries_empty(self):
        storage = PostgresStorage()

        async def test():
            result = await storage.write_entries([])
            return result

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertEqual(result, 0)


class TestVaultConfig(unittest.TestCase):
    """Test Vault configuration."""

    def test_default_config(self):
        config = VaultConfig()
        self.assertEqual(config.url, "http://localhost:8200")
        self.assertEqual(config.timeout, 30)
        self.assertTrue(config.verify_tls)

    def test_auth_config(self):
        auth = VaultAuthConfig(
            auth_method=VaultAuthMethod.APP_ROLE,
            app_role_id="role-123",
            app_secret_id="secret-456",
        )
        self.assertEqual(auth.auth_method, VaultAuthMethod.APP_ROLE)
        self.assertEqual(auth.app_role_id, "role-123")

    def test_to_dict(self):
        config = VaultConfig()
        d = config.to_dict()
        self.assertIsInstance(d, dict)
        self.assertIn("url", d)
        self.assertIn("timeout", d)

    def test_custom_config(self):
        config = VaultConfig(
            url="https://vault.prod.com",
            namespace="prod-team",
            secret_path="secret/data/production",
            auto_renew=True,
            renew_interval=600,
        )
        self.assertEqual(config.url, "https://vault.prod.com")
        self.assertEqual(config.namespace, "prod-team")
        self.assertTrue(config.auto_renew)


class TestRealVaultClient(unittest.TestCase):
    """Test HashiCorp Vault client."""

    def test_initialization(self):
        client = RealVaultClient()
        self.assertFalse(client.is_connected)  # Not connected until connect() called
        self.assertEqual(client.write_count, 0)
        self.assertEqual(client.read_count, 0)

    def test_connect_mock_mode(self):
        client = RealVaultClient()

        async def test():
            result = await client.connect()
            return result

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertTrue(result)
        self.assertTrue(client.is_connected)

    def test_write_secret(self):
        client = RealVaultClient()

        async def test():
            result = await client.write_secret("agent-keys/test-agent", {
                "private_key": "key-123",
                "public_key": "pub-456",
            })
            return result

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertTrue(result)
        self.assertEqual(client.write_count, 1)

    def test_read_secret(self):
        client = RealVaultClient()

        async def test():
            await client.write_secret("test/secret", {"key": "value"})
            result = await client.read_secret("test/secret")
            return result

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertIsNotNone(result)
        self.assertEqual(result["key"], "value")
        self.assertEqual(client.read_count, 1)

    def test_read_nonexistent_secret(self):
        client = RealVaultClient()

        async def test():
            result = await client.read_secret("nonexistent")
            return result

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertIsNone(result)

    def test_delete_secret(self):
        client = RealVaultClient()

        async def test():
            await client.write_secret("to-delete", {"data": "value"})
            delete_result = await client.delete_secret("to-delete")
            read_result = await client.read_secret("to-delete")
            return delete_result, read_result

        delete_result, read_result = asyncio.get_event_loop().run_until_complete(test())
        self.assertTrue(delete_result)
        self.assertIsNone(read_result)

    def test_list_secrets(self):
        client = RealVaultClient()

        async def test():
            await client.write_secret("group1/secret1", {"data": "v1"})
            await client.write_secret("group1/secret2", {"data": "v2"})
            await client.write_secret("group2/secret3", {"data": "v3"})
            result = await client.list_secrets()
            return result

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertIn("group1", result)
        self.assertIn("group2", result)

    def test_encrypt_decrypt(self):
        client = RealVaultClient()

        async def test():
            encrypted = await client.encrypt_data("sensitive data")
            decrypted = await client.decrypt_data(encrypted)
            return encrypted, decrypted

        encrypted, decrypted = asyncio.get_event_loop().run_until_complete(test())
        self.assertIsNotNone(encrypted)
        self.assertEqual(decrypted, "sensitive data")

    def test_generate_dynamic_creds(self):
        client = RealVaultClient()

        async def test():
            result = await client.generate_dynamic_db_creds("postgres-role")
            return result

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertIsNotNone(result)
        self.assertIn("username", result)
        self.assertIn("password", result)
        self.assertIn("lease_id", result)
        self.assertIn("ttl", result)

    def test_renew_token(self):
        client = RealVaultClient()

        async def test():
            result = await client.renew_token()
            return result

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertTrue(result)

    def test_get_stats(self):
        client = RealVaultClient()

        async def test():
            return await client.get_stats()

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertIn("connected", result)
        self.assertIn("write_count", result)
        self.assertIn("read_count", result)

    def test_close(self):
        client = RealVaultClient()

        async def test():
            await client.close()
            return not client.is_connected

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertTrue(result)


class TestTemporalConfig(unittest.TestCase):
    """Test Temporal workflow configuration."""

    def test_default_config(self):
        config = WorkflowConfig()
        self.assertEqual(config.server_url, "localhost:7233")
        self.assertEqual(config.namespace, "ajp")
        self.assertTrue(config.enable_mock)

    def test_to_dict(self):
        config = WorkflowConfig()
        d = config.to_dict()
        self.assertIsInstance(d, dict)
        self.assertIn("server_url", d)

    def test_custom_config(self):
        config = WorkflowConfig(
            server_url="temporal.prod.com:7233",
            namespace="production",
            workflow_timeout=7200,
            max_concurrent_workflows=200,
        )
        self.assertEqual(config.server_url, "temporal.prod.com:7233")
        self.assertEqual(config.max_concurrent_workflows, 200)


class TestTemporalWorkflowEngine(unittest.TestCase):
    """Test Temporal workflow engine."""

    def test_initialization(self):
        engine = TemporalWorkflowEngine()
        self.assertFalse(engine.is_connected)  # Not connected until connect() called

    def test_connect_mock_mode(self):
        engine = TemporalWorkflowEngine()

        async def test():
            return await engine.connect()

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertTrue(result)
        self.assertTrue(engine.is_connected)

    def test_register_activity(self):
        engine = TemporalWorkflowEngine()

        async def mock_activity(context):
            return {"status": "done"}

        engine.register_activity("test-activity", mock_activity)
        self.assertIn("test-activity", engine._activities)

    def test_register_workflow(self):
        engine = TemporalWorkflowEngine()

        async def mock_workflow(config):
            return {"entries": 100}

        engine.register_workflow(WorkflowType.BATCH_FLUSH.value, mock_workflow)
        self.assertIn(WorkflowType.BATCH_FLUSH.value, engine._workflow_defs)

    def test_start_workflow(self):
        engine = TemporalWorkflowEngine()

        async def test():
            workflow_id = await engine.start_workflow(
                WorkflowType.BATCH_FLUSH,
                {"entries": 100},
            )
            return workflow_id

        workflow_id = asyncio.get_event_loop().run_until_complete(test())
        self.assertIsNotNone(workflow_id)
        self.assertGreater(len(workflow_id), 0)

    def test_get_workflow_status(self):
        engine = TemporalWorkflowEngine()

        async def test():
            workflow_id = await engine.start_workflow(
                WorkflowType.BATCH_FLUSH,
                {},
            )
            await asyncio.sleep(0.2)
            status = await engine.get_workflow_status(workflow_id)
            return status

        status = asyncio.get_event_loop().run_until_complete(test())
        self.assertIsNotNone(status)

    def test_cancel_workflow(self):
        engine = TemporalWorkflowEngine()

        async def test():
            workflow_id = await engine.start_workflow(
                WorkflowType.BATCH_FLUSH,
                {},
            )
            result = await engine.cancel_workflow(workflow_id)
            return result

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertTrue(result)

    def test_cancel_nonexistent_workflow(self):
        engine = TemporalWorkflowEngine()

        async def test():
            return await engine.cancel_workflow("nonexistent-id")

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertFalse(result)

    def test_add_checkpoint(self):
        engine = TemporalWorkflowEngine()

        async def test():
            workflow_id = await engine.start_workflow(
                WorkflowType.BATCH_FLUSH,
                {},
            )
            result = await engine.add_checkpoint(workflow_id, {
                "type": "progress",
                "progress": 50,
            })
            checkpoints = await engine.get_checkpoints(workflow_id)
            return result, checkpoints

        result, checkpoints = asyncio.get_event_loop().run_until_complete(test())
        self.assertTrue(result)
        self.assertGreater(len(checkpoints), 0)

    def test_execute_saga(self):
        engine = TemporalWorkflowEngine()

        async def test():
            workflow_id = await engine.start_workflow(
                WorkflowType.CUSTOM,
                {},
            )
            operations = [
                {
                    "action": "step1",
                    "compensate": "compensate1",
                    "context": {"data": "test1"},
                },
                {
                    "action": "step2",
                    "compensate": "compensate2",
                    "context": {"data": "test2"},
                },
            ]
            result = await engine.execute_saga(workflow_id, operations)
            return result

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertTrue(result["success"])
        self.assertEqual(result["completed_steps"], 2)

    def test_list_workflows(self):
        engine = TemporalWorkflowEngine()

        async def test():
            await engine.start_workflow(WorkflowType.BATCH_FLUSH, {})
            await engine.start_workflow(WorkflowType.CHAIN_REBUILD, {})
            all_workflows = await engine.list_workflows()
            filtered = await engine.list_workflows(workflow_type=WorkflowType.BATCH_FLUSH)
            return all_workflows, filtered

        all_workflows, filtered = asyncio.get_event_loop().run_until_complete(test())
        self.assertEqual(len(all_workflows), 2)
        self.assertEqual(len(filtered), 1)

    def test_get_stats(self):
        engine = TemporalWorkflowEngine()

        async def test():
            return await engine.get_stats()

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertIn("connected", result)
        self.assertIn("total_workflows", result)
        self.assertIn("status_counts", result)

    def test_close(self):
        engine = TemporalWorkflowEngine()

        async def test():
            await engine.close()
            return not engine.is_connected

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertTrue(result)


class TestOTelConfig(unittest.TestCase):
    """Test OpenTelemetry configuration."""

    def test_default_config(self):
        config = OTelConfig()
        self.assertEqual(config.otlp_endpoint, "http://localhost:4317")
        self.assertEqual(config.service_name, "ajp-journal")
        self.assertTrue(config.enable_tracing)

    def test_to_dict(self):
        config = OTelConfig()
        d = config.to_dict()
        self.assertIsInstance(d, dict)
        self.assertIn("otlp_endpoint", d)

    def test_custom_config(self):
        config = OTelConfig(
            otlp_endpoint="http://otel.prod.com:4317",
            service_name="ajp-production",
            trace_sample_rate=0.5,
            metric_export_interval=30,
        )
        self.assertEqual(config.trace_sample_rate, 0.5)
        self.assertEqual(config.metric_export_interval, 30)


class TestOTLPExporter(unittest.TestCase):
    """Test OpenTelemetry OTLP exporter."""

    def test_initialization(self):
        exporter = OTLPExporter()
        self.assertFalse(exporter.is_connected)  # Not connected until connect() called

    def test_connect_mock_mode(self):
        exporter = OTLPExporter()

        async def test():
            return await exporter.connect()

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertTrue(result)
        self.assertTrue(exporter.is_connected)

    def test_start_trace(self):
        exporter = OTLPExporter()

        async def test():
            trace_id = exporter.start_trace("test-trace")
            return trace_id

        trace_id = asyncio.get_event_loop().run_until_complete(test())
        self.assertIsNotNone(trace_id)
        self.assertGreater(len(trace_id), 0)

    def test_create_span(self):
        exporter = OTLPExporter()

        async def test():
            trace_id = exporter.start_trace("test-trace")
            span_id = exporter.create_span(
                trace_id,
                "test-span",
                kind=SpanKind.SERVER,
                attributes={"http.method": "GET"},
            )
            return span_id

        span_id = asyncio.get_event_loop().run_until_complete(test())
        self.assertIsNotNone(span_id)

    def test_end_span(self):
        exporter = OTLPExporter()

        async def test():
            trace_id = exporter.start_trace("test-trace")
            span_id = exporter.create_span(trace_id, "test-span")
            exporter.end_span(span_id, SpanStatus.OK)
            return True

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertTrue(result)

    def test_add_span_event(self):
        exporter = OTLPExporter()

        async def test():
            trace_id = exporter.start_trace("test-trace")
            span_id = exporter.create_span(trace_id, "test-span")
            exporter.add_span_event(span_id, "event-1", {"key": "value"})
            exporter.end_span(span_id)
            return True

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertTrue(result)

    def test_record_counter(self):
        exporter = OTLPExporter()

        async def test():
            exporter.record_metric("requests.total", 1.0, MetricType.COUNTER)
            exporter.increment_counter("requests.total")
            counter = await exporter.get_counter("requests.total")
            return counter

        counter = asyncio.get_event_loop().run_until_complete(test())
        self.assertEqual(counter, 2.0)

    def test_record_gauge(self):
        exporter = OTLPExporter()

        async def test():
            exporter.set_gauge("active_connections", 42.0)
            gauge = await exporter.get_gauge("active_connections")
            return gauge

        gauge = asyncio.get_event_loop().run_until_complete(test())
        self.assertEqual(gauge, 42.0)

    def test_record_histogram(self):
        exporter = OTLPExporter()

        async def test():
            exporter.record_histogram("response_time", 100.0)
            exporter.record_histogram("response_time", 200.0)
            exporter.record_histogram("response_time", 150.0)
            stats = await exporter.get_histogram_stats("response_time")
            return stats

        stats = asyncio.get_event_loop().run_until_complete(test())
        self.assertEqual(stats["count"], 3)
        self.assertEqual(stats["min"], 100.0)
        self.assertEqual(stats["max"], 200.0)
        self.assertEqual(stats["mean"], 150.0)

    def test_export_traces(self):
        exporter = OTLPExporter()

        async def test():
            exported = await exporter.export_traces()
            return exported

        exported = asyncio.get_event_loop().run_until_complete(test())
        self.assertGreaterEqual(exported, 0)

    def test_export_metrics(self):
        exporter = OTLPExporter()

        async def test():
            exporter.record_metric("test.metric", 1.0)
            exported = await exporter.export_metrics()
            return exported

        exported = asyncio.get_event_loop().run_until_complete(test())
        self.assertEqual(exported, 1)

    def test_export_all(self):
        exporter = OTLPExporter()

        async def test():
            result = await exporter.export_all()
            return result

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertIn("traces", result)
        self.assertIn("metrics", result)

    def test_get_trace(self):
        exporter = OTLPExporter()

        async def test():
            trace_id = exporter.start_trace("test-trace")
            trace = await exporter.get_trace(trace_id)
            return trace

        trace = asyncio.get_event_loop().run_until_complete(test())
        self.assertIsNotNone(trace)
        self.assertEqual(trace["service_name"], "ajp-journal")

    def test_get_traces(self):
        exporter = OTLPExporter()

        async def test():
            exporter.start_trace("trace-1")
            exporter.start_trace("trace-2")
            traces = await exporter.get_traces(limit=5)
            return traces

        traces = asyncio.get_event_loop().run_until_complete(test())
        self.assertEqual(len(traces), 2)

    def test_get_metrics(self):
        exporter = OTLPExporter()

        async def test():
            exporter.record_metric("test.metric", 1.0, MetricType.COUNTER)
            metrics = await exporter.get_metrics(metric_name="test.metric")
            return metrics

        metrics = asyncio.get_event_loop().run_until_complete(test())
        self.assertEqual(len(metrics), 1)

    def test_log_with_trace(self):
        exporter = OTLPExporter()

        async def test():
            trace_id = exporter.start_trace("test-trace")
            span_id = exporter.create_span(trace_id, "test-span")
            exporter.log_with_trace("INFO", "Test message", trace_id, span_id)
            exporter.end_span(span_id)
            return True

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertTrue(result)

    def test_get_stats(self):
        exporter = OTLPExporter()

        async def test():
            return await exporter.get_stats()

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertIn("connected", result)
        self.assertIn("trace_count", result)
        self.assertIn("metric_count", result)

    def test_close(self):
        exporter = OTLPExporter()

        async def test():
            await exporter.close()
            return not exporter.is_connected

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertTrue(result)


class TestIntegration(unittest.TestCase):
    """Integration tests between components."""

    def test_vault_with_temporal(self):
        """Test Vault and Temporal working together."""
        vault = RealVaultClient()
        engine = TemporalWorkflowEngine()

        async def test():
            # Write secret
            await vault.write_secret("workflow-config", {"max_retries": 3})

            # Start workflow
            workflow_id = await engine.start_workflow(
                WorkflowType.CUSTOM,
                {"config_source": "vault"},
            )

            # Read secret back
            config = await vault.read_secret("workflow-config")

            return config is not None and workflow_id is not None

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertTrue(result)

    def test_otel_tracing_workflow(self):
        """Test OpenTelemetry tracing a workflow execution."""
        exporter = OTLPExporter()
        engine = TemporalWorkflowEngine()

        async def test():
            trace_id = exporter.start_trace("workflow-execution")
            span_id = exporter.create_span(
                trace_id,
                "start-workflow",
                kind=SpanKind.CLIENT,
            )

            workflow_id = await engine.start_workflow(
                WorkflowType.BATCH_FLUSH,
                {"entries": 50},
            )

            exporter.add_span_event(span_id, "workflow-started", {"workflow_id": workflow_id})
            exporter.end_span(span_id)

            return workflow_id is not None

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertTrue(result)

    def test_full_pipeline(self):
        """Test full pipeline: Vault + Temporal + OpenTelemetry."""
        vault = RealVaultClient()
        engine = TemporalWorkflowEngine()
        exporter = OTLPExporter()

        async def test():
            # Start trace
            trace_id = exporter.start_trace("full-pipeline")
            span_id = exporter.create_span(trace_id, "pipeline-execution")

            # Store config in Vault
            await vault.write_secret("pipeline-config", {
                "batch_size": 100,
                "timeout": 300,
            })

            # Start workflow
            workflow_id = await engine.start_workflow(
                WorkflowType.BATCH_FLUSH,
                {"batch_size": 100},
            )

            # Record metrics
            exporter.increment_counter("pipeline.started")
            exporter.set_gauge("pipeline.active_workflows", 1)

            # End trace
            exporter.end_span(span_id)

            return True

        result = asyncio.get_event_loop().run_until_complete(test())
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
