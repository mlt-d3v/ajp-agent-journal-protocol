"""Phase 5 tests - Temporal Workflow + OpenTelemetry Bridge."""
import sys
import asyncio
import unittest
from datetime import datetime
sys.path.insert(0, "/Users/michaelthomas/.hermes/skills/ajp-agent-journal-protocol/src")

from ajp.workflow.engine import (
    WorkflowEngine, WorkflowDefinition, WorkflowStep,
    WorkflowState, Checkpoint, CheckpointType, RetryPolicy,
)
from ajp.workflow.otel_bridge import (
    Tracer, Span, SpanKind, SpanStatus, SpanEvent, SpanAttribute,
    MetricsExporter,
)


class TestWorkflowStep(unittest.TestCase):
    def test_create_step(self):
        step = WorkflowStep(name="test", handler=lambda ctx: "result")
        self.assertEqual(step.name, "test")
        self.assertEqual(step.retry_count, 3)

    def test_step_with_retry(self):
        step = WorkflowStep(name="test", handler=lambda ctx: "result", retry_count=5, retry_delay=0.5)
        self.assertEqual(step.retry_count, 5)
        self.assertEqual(step.retry_delay, 0.5)

    def test_step_with_compensation(self):
        comp = lambda ctx: None
        step = WorkflowStep(name="test", handler=lambda ctx: "result", compensating=comp)
        self.assertIsNotNone(step.compensating)


class TestWorkflowDefinition(unittest.TestCase):
    def test_create_definition(self):
        defn = WorkflowDefinition(name="test_workflow")
        self.assertEqual(defn.name, "test_workflow")
        self.assertEqual(len(defn.steps), 0)

    def test_add_steps(self):
        defn = WorkflowDefinition(name="test")
        defn.add_step(WorkflowStep(name="step1", handler=lambda ctx: "a"))
        defn.add_step(WorkflowStep(name="step2", handler=lambda ctx: "b"))
        self.assertEqual(len(defn.steps), 2)

    def test_retry_policy(self):
        policy = RetryPolicy(max_attempts=5, backoff_factor=3.0)
        defn = WorkflowDefinition(name="test", retry_policy=policy)
        self.assertEqual(defn.retry_policy.max_attempts, 5)


class TestWorkflowEngine(unittest.IsolatedAsyncioTestCase):
    async def test_register_workflow(self):
        engine = WorkflowEngine()
        defn = WorkflowDefinition(name="test")
        wid = engine.register_workflow(defn)
        self.assertIsNotNone(wid)
        status = engine.get_status(wid)
        self.assertEqual(status["state"], "pending")

    async def test_execute_simple_workflow(self):
        engine = WorkflowEngine()
        results = []
        defn = WorkflowDefinition(name="simple")
        defn.add_step(WorkflowStep(name="step1", handler=lambda ctx: results.append(1)))
        defn.add_step(WorkflowStep(name="step2", handler=lambda ctx: results.append(2)))
        wid = engine.register_workflow(defn)
        await engine.execute(wid)
        self.assertEqual(results, [1, 2])
        status = engine.get_status(wid)
        self.assertEqual(status["state"], "completed")

    async def test_execute_async_workflow(self):
        engine = WorkflowEngine()
        defn = WorkflowDefinition(name="async_test")
        async def async_handler(ctx):
            await asyncio.sleep(0.01)
            return "async_result"
        defn.add_step(WorkflowStep(name="async_step", handler=async_handler))
        wid = engine.register_workflow(defn)
        result = await engine.execute(wid)
        self.assertIn("async_step", result)

    async def test_workflow_retry(self):
        engine = WorkflowEngine()
        call_count = [0]
        def flaky_handler(ctx):
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("not yet")
            return "success"
        defn = WorkflowDefinition(name="retry_test")
        defn.add_step(WorkflowStep(name="flaky", handler=flaky_handler, retry_count=5))
        wid = engine.register_workflow(defn)
        result = await engine.execute(wid)
        self.assertEqual(call_count[0], 3)
        self.assertEqual(engine.get_status(wid)["state"], "completed")

    async def test_workflow_failure(self):
        engine = WorkflowEngine()
        defn = WorkflowDefinition(name="fail_test")
        defn.add_step(WorkflowStep(name="fail", handler=lambda ctx: (_ for _ in ()).throw(ValueError("fail")), retry_count=1))
        wid = engine.register_workflow(defn)
        result = await engine.execute(wid)
        self.assertIsNone(result)
        self.assertEqual(engine.get_status(wid)["state"], "failed")

    async def test_workflow_cancel(self):
        engine = WorkflowEngine()
        defn = WorkflowDefinition(name="cancel_test")
        defn.add_step(WorkflowStep(name="step1", handler=lambda ctx: None))
        wid = engine.register_workflow(defn)
        await engine.cancel(wid)
        self.assertEqual(engine.get_status(wid)["state"], "cancelled")

    async def test_checkpoint_saving(self):
        engine = WorkflowEngine()
        defn = WorkflowDefinition(name="checkpoint_test")
        defn.add_step(WorkflowStep(name="s1", handler=lambda ctx: "a"))
        defn.add_step(WorkflowStep(name="s2", handler=lambda ctx: "b"))
        wid = engine.register_workflow(defn)
        await engine.execute(wid)
        cps = engine.get_checkpoints(wid)
        self.assertEqual(len(cps), 2)

    async def test_checkpoint_types(self):
        cp = Checkpoint(id="cp1", workflow_id="w1", step_index=0, data={"key": "val"})
        self.assertEqual(cp.checkpoint_type, CheckpointType.SAVEPOINT)
        for ct in CheckpointType:
            self.assertIsNotNone(ct.value)

    async def test_workflow_history(self):
        engine = WorkflowEngine()
        defn = WorkflowDefinition(name="history_test")
        wid = engine.register_workflow(defn)
        history = engine.get_history(wid)
        self.assertGreater(len(history), 0)
        self.assertEqual(history[0]["event"], "registered")

    async def test_unknown_workflow(self):
        engine = WorkflowEngine()
        self.assertIsNone(engine.get_status("unknown"))

    async def test_workflow_context_passing(self):
        engine = WorkflowEngine()
        defn = WorkflowDefinition(name="context_test")
        defn.add_step(WorkflowStep(name="set", handler=lambda ctx: "done"))
        wid = engine.register_workflow(defn)
        ctx = {"initial": True}
        result = await engine.execute(wid, context=ctx)
        self.assertIn("set", result)

    async def test_step_timeout(self):
        engine = WorkflowEngine()
        defn = WorkflowDefinition(name="timeout_test")
        async def slow_handler(ctx):
            await asyncio.sleep(10)
        defn.add_step(WorkflowStep(name="slow", handler=slow_handler, timeout=0.1, retry_count=1))
        wid = engine.register_workflow(defn)
        await engine.execute(wid)
        self.assertEqual(engine.get_status(wid)["state"], "failed")

    async def test_compensation_on_failure(self):
        engine = WorkflowEngine()
        compensated = []
        defn = WorkflowDefinition(name="compensation_test")
        defn.add_step(WorkflowStep(name="s1", handler=lambda ctx: compensated.append("s1")))
        defn.add_step(WorkflowStep(
            name="s2", handler=lambda ctx: (_ for _ in ()).throw(ValueError("fail")),
            retry_count=1,
            compensating=lambda ctx: compensated.append("comp_s2"),
        ))
        wid = engine.register_workflow(defn)
        await engine.execute(wid)
        self.assertIn("s1", compensated)

    async def test_multiple_workflows(self):
        engine = WorkflowEngine()
        wids = []
        for i in range(3):
            defn = WorkflowDefinition(name=f"wf_{i}")
            defn.add_step(WorkflowStep(name="step", handler=lambda ctx: i))
            wids.append(engine.register_workflow(defn))
        for wid in wids:
            await engine.execute(wid)
        for wid in wids:
            self.assertEqual(engine.get_status(wid)["state"], "completed")

    async def test_checkpoint_serialization(self):
        cp = Checkpoint(id="cp1", workflow_id="w1", step_index=5, data={"result": "ok"})
        d = cp.to_dict()
        restored = Checkpoint.from_dict(d)
        self.assertEqual(restored.id, cp.id)
        self.assertEqual(restored.step_index, cp.step_index)

    async def test_workflow_step_results(self):
        engine = WorkflowEngine()
        defn = WorkflowDefinition(name="results_test")
        defn.add_step(WorkflowStep(name="a", handler=lambda ctx: 10))
        defn.add_step(WorkflowStep(name="b", handler=lambda ctx: 20))
        wid = engine.register_workflow(defn)
        result = await engine.execute(wid)
        self.assertEqual(result["a"], 10)
        self.assertEqual(result["b"], 20)


class TestSpan(unittest.TestCase):
    def test_create_span(self):
        span = Span(trace_id="t1", span_id="s1", name="test")
        self.assertEqual(span.name, "test")
        self.assertTrue(span.is_root)

    def test_span_duration(self):
        span = Span(trace_id="t1", span_id="s1", name="test", start_time=1.0, end_time=2.5)
        self.assertEqual(span.duration, 1.5)

    def test_span_end(self):
        span = Span(trace_id="t1", span_id="s1", name="test")
        span.end()
        self.assertIsNotNone(span.duration)

    def test_add_attribute(self):
        span = Span(trace_id="t1", span_id="s1", name="test")
        span.add_attribute("key", "value")
        self.assertEqual(len(span.attributes), 1)

    def test_add_event(self):
        span = Span(trace_id="t1", span_id="s1", name="test")
        span.add_event("event1")
        self.assertEqual(len(span.events), 1)

    def test_set_status(self):
        span = Span(trace_id="t1", span_id="s1", name="test")
        span.set_status(SpanStatus.ERROR, "something went wrong")
        self.assertEqual(span.status, SpanStatus.ERROR)

    def test_to_dict(self):
        span = Span(trace_id="t1", span_id="s1", name="test")
        span.end()
        d = span.to_dict()
        self.assertEqual(d["trace_id"], "t1")
        self.assertEqual(d["name"], "test")

    def test_child_span(self):
        parent = Span(trace_id="t1", span_id="s1", name="parent")
        child = Span(trace_id="t1", span_id="s2", parent_span_id="s1", name="child")
        self.assertFalse(child.is_root)


class TestTracer(unittest.TestCase):
    def test_start_span(self):
        tracer = Tracer(service_name="test-service")
        span = tracer.start_span("test-operation")
        self.assertEqual(span.name, "test-operation")
        self.assertTrue(span.is_root)

    def test_end_span(self):
        tracer = Tracer()
        span = tracer.start_span("test")
        tracer.end_span(span.span_id)
        self.assertIsNotNone(span.duration)

    def test_create_child_span(self):
        tracer = Tracer()
        parent = tracer.start_span("parent")
        child = tracer.create_child_span("child")
        self.assertEqual(child.parent_span_id, parent.span_id)
        self.assertEqual(child.trace_id, parent.trace_id)

    def test_get_trace(self):
        tracer = Tracer()
        tracer.start_span("op1")
        tracer.create_child_span("op2")
        tracer.create_child_span("op3")
        trace = tracer.get_trace(tracer._active_span.trace_id)
        self.assertEqual(len(trace), 3)

    def test_export_spans(self):
        tracer = Tracer()
        tracer.start_span("op1")
        tracer.end_span()
        exported = tracer.export_spans()
        self.assertEqual(len(exported), 1)
        self.assertEqual(exported[0]["name"], "op1")

    def test_stats(self):
        tracer = Tracer()
        tracer.start_span("s1")
        tracer.start_span("s2")
        tracer.end_span()
        stats = tracer.get_stats()
        self.assertEqual(stats["total_spans"], 2)
        self.assertEqual(stats["completed"], 1)

    def test_span_kinds(self):
        for kind in SpanKind:
            self.assertIsNotNone(kind.value)

    def test_span_statuses(self):
        for status in SpanStatus:
            self.assertIsNotNone(status.value)

    def test_service_name(self):
        tracer = Tracer(service_name="my-agent")
        span = tracer.start_span("test")
        self.assertEqual(span.resource["service.name"], "my-agent")

    def test_export_by_trace(self):
        tracer = Tracer()
        s1 = tracer.start_span("t1-op")
        tracer.end_span()
        s2 = tracer.start_span("t2-op")
        tracer.end_span()
        trace1 = tracer.export_spans(s1.trace_id)
        self.assertEqual(len(trace1), 1)


class TestMetricsExporter(unittest.TestCase):
    def test_counter(self):
        me = MetricsExporter()
        me.increment_counter("requests")
        me.increment_counter("requests")
        self.assertEqual(me.get_counter("requests"), 2.0)

    def test_counter_with_value(self):
        me = MetricsExporter()
        me.increment_counter("bytes", 100.0)
        self.assertEqual(me.get_counter("bytes"), 100.0)

    def test_gauge(self):
        me = MetricsExporter()
        me.set_gauge("cpu", 45.5)
        self.assertEqual(me.get_gauge("cpu"), 45.5)

    def test_histogram(self):
        me = MetricsExporter()
        for v in [1.0, 2.0, 3.0, 4.0, 5.0]:
            me.record_histogram("latency", v)
        stats = me.get_histogram_stats("latency")
        self.assertEqual(stats["count"], 5)
        self.assertEqual(stats["min"], 1.0)
        self.assertEqual(stats["max"], 5.0)
        self.assertEqual(stats["mean"], 3.0)

    def test_labels(self):
        me = MetricsExporter()
        me.increment_counter("requests", labels={"method": "GET"})
        me.increment_counter("requests", labels={"method": "POST"})
        self.assertEqual(me.get_counter("requests", labels={"method": "GET"}), 1.0)
        self.assertEqual(me.get_counter("requests", labels={"method": "POST"}), 1.0)

    def test_export_all(self):
        me = MetricsExporter()
        me.increment_counter("c1")
        me.set_gauge("g1", 5.0)
        me.record_histogram("h1", 10.0)
        exported = me.export_all()
        self.assertIn("counters", exported)
        self.assertIn("gauges", exported)
        self.assertIn("histograms", exported)

    def test_empty_histogram(self):
        me = MetricsExporter()
        stats = me.get_histogram_stats("nonexistent")
        self.assertEqual(stats["count"], 0)

    def test_gauge_update(self):
        me = MetricsExporter()
        me.set_gauge("temp", 20.0)
        me.set_gauge("temp", 25.0)
        self.assertEqual(me.get_gauge("temp"), 25.0)

    def test_counter_default(self):
        me = MetricsExporter()
        self.assertEqual(me.get_counter("unknown"), 0.0)

    def test_gauge_default(self):
        me = MetricsExporter()
        self.assertEqual(me.get_gauge("unknown"), 0.0)


class TestWorkflowIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_workflow_with_tracing(self):
        engine = WorkflowEngine()
        tracer = Tracer(service_name="ajp-workflow")
        defn = WorkflowDefinition(name="traced_workflow")
        tracer.start_span("workflow.start")
        defn.add_step(WorkflowStep(name="step1", handler=lambda ctx: None))
        defn.add_step(WorkflowStep(name="step2", handler=lambda ctx: None))
        wid = engine.register_workflow(defn)
        await engine.execute(wid)
        tracer.create_child_span("workflow.complete")
        tracer.end_span()
        stats = tracer.get_stats()
        self.assertGreater(stats["total_spans"], 0)

    async def test_workflow_with_metrics(self):
        engine = WorkflowEngine()
        metrics = MetricsExporter()
        defn = WorkflowDefinition(name="metric_workflow")
        defn.add_step(WorkflowStep(name="s1", handler=lambda ctx: None))
        defn.add_step(WorkflowStep(name="s2", handler=lambda ctx: None))
        wid = engine.register_workflow(defn)
        start = __import__("time").monotonic()
        await engine.execute(wid)
        duration = __import__("time").monotonic() - start
        metrics.increment_counter("workflows_completed")
        metrics.record_histogram("workflow_duration", duration)
        self.assertEqual(metrics.get_counter("workflows_completed"), 1.0)
        hist = metrics.get_histogram_stats("workflow_duration")
        self.assertEqual(hist["count"], 1)

    async def test_full_pipeline(self):
        engine = WorkflowEngine()
        tracer = Tracer()
        metrics = MetricsExporter()
        steps_executed = []
        defn = WorkflowDefinition(name="pipeline")
        for i in range(3):
            defn.add_step(WorkflowStep(name=f"step_{i}", handler=lambda ctx, n=i: steps_executed.append(n)))
        wid = engine.register_workflow(defn)
        tracer.start_span("pipeline.start")
        await engine.execute(wid)
        tracer.end_span()
        metrics.increment_counter("pipeline_runs")
        self.assertEqual(len(steps_executed), 3)
        self.assertEqual(engine.get_status(wid)["state"], "completed")
        self.assertEqual(metrics.get_counter("pipeline_runs"), 1.0)

    async def test_error_handling_pipeline(self):
        engine = WorkflowEngine()
        tracer = Tracer()
        metrics = MetricsExporter()
        defn = WorkflowDefinition(name="error_pipeline")
        defn.add_step(WorkflowStep(name="good", handler=lambda ctx: None))
        defn.add_step(WorkflowStep(name="bad", handler=lambda ctx: (_ for _ in ()).throw(RuntimeError("err")), retry_count=1))
        wid = engine.register_workflow(defn)
        tracer.start_span("error_pipeline")
        await engine.execute(wid)
        tracer._active_span.set_status(SpanStatus.ERROR, "workflow failed")
        tracer.end_span()
        metrics.increment_counter("pipeline_errors")
        self.assertEqual(engine.get_status(wid)["state"], "failed")
        self.assertEqual(metrics.get_counter("pipeline_errors"), 1.0)


if __name__ == "__main__":
    unittest.main()
