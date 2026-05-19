# ajp/workflow/workflow_definition.py
"""
Defines the structure for a multi-step, multi-agent workflow.
This module is responsible for defining the steps and their sequence.
"""
from typing import List, Callable, Dict, Any
from abc import ABC, abstractmethod

class WorkflowStep(ABC):
    """Represents a single, defined step in the workflow chain."""
    def __init__(self, name: str, handler: Callable[[Dict[str, Any]], Any]):
        self.name = name
        self.handler = handler # Python callable that takes current context and returns result

    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> Any:
        """Executes the step logic, updating the context."""
        pass

class WorkflowDefinition:
    """Container for a sequence of steps."""
    
    def __init__(self, name: str, initial_context: Dict[str, Any]):
        self.name = name
        self.steps: List[WorkflowStep] = []
        self.initial_context = initial_context

    def add_step(self, step: WorkflowStep):
        """Adds a step to the workflow sequence."""
        if not isinstance(step, WorkflowStep):
            raise TypeError("Must add an instance of WorkflowStep.")
        self.steps.append(step)

    def get_context_history(self) -> List[Dict[str, Any]]:
        """Returns the history of context updates."""
        return []

# Example use of the handler:
# def task_handler(context):
#     # Example: read a file using the injected FileToolService
#     # result = context['file_service'].read(context['file_path'])
#     return {"result": f"Processed {len(context['data'])} items."}