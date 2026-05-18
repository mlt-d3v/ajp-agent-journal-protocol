"""Temporal-like workflow engine for orchestrating agent journaling workflows."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import asyncio
import hashlib
import json
import time


class WorkflowState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class CheckpointType(Enum):
    SAVEPOINT = "savepoint"
    BARRIER = "barrier"
    COMPENSATION = "compensation"


@dataclass
class Checkpoint:
    id: str
    workflow_id: str
    step_index: int
    data: dict
    timestamp: datetime = field(default_factory=datetime.utcnow)
    checkpoint_type: CheckpointType = CheckpointType.SAVEPOINT

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "step_index": self.step_index,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "type": self.checkpoint_type.value,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Checkpoint":
        d = d.copy()
        d["timestamp"] = datetime.fromisoformat(d["timestamp"])
        d["checkpoint_type"] = CheckpointType(d.pop("type"))
        return cls(**d)


@dataclass
class WorkflowStep:
    name: str
    handler: Callable
    retry_count: int = 3
    retry_delay: float = 1.0
    timeout: float = 30.0
    on_failure: Optional[Callable] = None
    compensating: Optional[Callable] = None


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    backoff_factor: float = 2.0
    max_delay: float = 60.0
    retryable_errors: Optional[List[str]] = None


@dataclass
class WorkflowDefinition:
    name: str
    steps: List[WorkflowStep] = field(default_factory=list)
    retry_policy: Optional[RetryPolicy] = None
    idempotency_key: Optional[str] = None

    def add_step(self, step: WorkflowStep):
        self.steps.append(step)


class WorkflowEngine:
    def __init__(self):
        self._workflows: Dict[str, dict] = {}
        self._checkpoints: Dict[str, List[Checkpoint]] = {}
        self._history: List[dict] = []

    def register_workflow(self, definition: WorkflowDefinition) -> str:
        workflow_id = hashlib.sha256(
            f"{definition.name}-{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]
        self._workflows[workflow_id] = {
            "definition": definition,
            "state": WorkflowState.PENDING,
            "current_step": 0,
            "result": None,
            "error": None,
            "created_at": datetime.utcnow(),
        }
        self._checkpoints[workflow_id] = []
        self._history.append({
            "workflow_id": workflow_id,
            "event": "registered",
            "timestamp": datetime.utcnow().isoformat(),
        })
        return workflow_id

    async def execute(self, workflow_id: str, context: Optional[dict] = None) -> Any:
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        workflow["state"] = WorkflowState.RUNNING
        context = context or {}
        for i, step in enumerate(workflow["definition"].steps):
            workflow["current_step"] = i
            retry_policy = workflow["definition"].retry_policy or RetryPolicy()
            max_attempts = step.retry_count or retry_policy.max_attempts
            for attempt in range(max_attempts):
                try:
                    result = await asyncio.wait_for(
                        self._run_step(step, context, workflow_id),
                        timeout=step.timeout,
                    )
                    context["step_results"] = context.get("step_results", {})
                    context["step_results"][step.name] = result
                    await self._save_checkpoint(workflow_id, i, {"result": str(result)[:200]})
                    break
                except asyncio.TimeoutError:
                    if attempt < max_attempts - 1:
                        delay = min(retry_policy.backoff_factor ** attempt, retry_policy.max_delay)
                        await asyncio.sleep(delay)
                    else:
                        workflow["state"] = WorkflowState.FAILED
                        workflow["error"] = f"Step {step.name} timed out"
                        await self._compensate(workflow_id, i, context)
                        return None
                except Exception as e:
                    if step.on_failure:
                        await step.on_failure(e, context)
                    if attempt < max_attempts - 1:
                        delay = min(retry_policy.backoff_factor ** attempt, retry_policy.max_delay)
                        await asyncio.sleep(delay)
                    else:
                        workflow["state"] = WorkflowState.FAILED
                        workflow["error"] = str(e)
                        await self._compensate(workflow_id, i, context)
                        return None
            else:
                workflow["state"] = WorkflowState.FAILED
                workflow["error"] = f"Step {step.name} exhausted retries"
                await self._compensate(workflow_id, i, context)
                return None
        workflow["state"] = WorkflowState.COMPLETED
        return context.get("step_results")

    async def _run_step(self, step: WorkflowStep, context: dict, workflow_id: str) -> Any:
        result = step.handler(context)
        if asyncio.iscoroutine(result) or asyncio.iscoroutinefunction(step.handler):
            return await result
        return result

    async def _save_checkpoint(self, workflow_id: str, step_index: int, data: dict):
        cp = Checkpoint(
            id=hashlib.sha256(f"{workflow_id}-{step_index}-{time.monotonic()}".encode()).hexdigest()[:12],
            workflow_id=workflow_id,
            step_index=step_index,
            data=data,
        )
        self._checkpoints[workflow_id].append(cp)

    async def _compensate(self, workflow_id: str, failed_step: int, context: dict):
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return
        for i in range(failed_step - 1, -1, -1):
            step = workflow["definition"].steps[i]
            if step.compensating:
                try:
                    comp_result = step.compensating(context)
                    if asyncio.iscoroutine(comp_result):
                        await comp_result
                except Exception:
                    pass

    async def cancel(self, workflow_id: str):
        workflow = self._workflows.get(workflow_id)
        if workflow and workflow["state"] in (WorkflowState.PENDING, WorkflowState.RUNNING):
            await self._compensate(workflow_id, workflow["current_step"], {})
            workflow["state"] = WorkflowState.CANCELLED

    def get_status(self, workflow_id: str) -> Optional[dict]:
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return None
        return {
            "state": workflow["state"].value,
            "current_step": workflow["current_step"],
            "error": workflow["error"],
            "checkpoints": len(self._checkpoints.get(workflow_id, [])),
        }

    def get_checkpoints(self, workflow_id: str) -> List[Checkpoint]:
        return self._checkpoints.get(workflow_id, [])

    def get_history(self, workflow_id: str) -> List[dict]:
        return [h for h in self._history if h["workflow_id"] == workflow_id]
