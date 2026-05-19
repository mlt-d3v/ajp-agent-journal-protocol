# ajp/workflow/workflow_engine.py
"""
The central execution engine for defining and running complex, multi-step AI workflows.
Orchestrates the flow of control and tracks state changes across distinct workflow steps.
"""
from typing import Dict, Any
from .workflow_definition import WorkflowDefinition, WorkflowStep

class WorkflowEngine:
    """A machine that runs WorkflowDefinition sequences."""
    
    def __init__(self, initial_context: Dict[str, Any]):
        self.initial_context = initial_context
        self.context: Dict[str, Any] = initial_context.copy()

    def register_workflow(self, definition: WorkflowDefinition) -> str:
        """Simulates registering a workflow to provide a traceable ID."""
        # In a real system, this would save metadata to a central workflow registry DB
        workflow_id = f"wf-{definition.name}-{hash(str(list(definition.steps)))}"
        print(f"[AJP-WE] Workflow '{definition.name}' registered with ID: {workflow_id}")
        return workflow_id

    def run_workflow(self, definition: WorkflowDefinition) -> Dict[str, Any]:
        """
        Executes a defined workflow sequence start-to-end.
        Returns the final context state.
        """
        print(f"\n[AJP-WE] Starting execution for workflow: {definition.name}...")
        
        current_context = self.initial_context.copy()
        history: List[Dict[str, Any]] = []

        for i, step in enumerate(definition.steps):
            step_name = f"step_{i}_{step.name}"
            print(f"--- Executing Step {i+1}/{len(definition.steps)}: {step.name} ---")
            
            try:
                # Execute the step's logic using the current context
                step_result = step.execute(current_context)
                
                # Update context with the step's output
                current_context.update(step_result)
                history.append({"step": step_name, "output": step_result, "status": "SUCCESS"})
                print(f"Step {i+1} completed. New context available.")
            except Exception as e:
                # IMPORTANT: Log the failure and stop the workflow gracefully
                history.append({"step": step_name, "output": str(e), "status": "FAILURE"})
                print(f"!! CRITICAL FAILURE at Step {i+1}: {e}")
                break

        print(f"[AJP-WE] Workflow execution finished. Final state successfully achieved.")
        return current_context

# Example usage (for testing):
# context = {"input_file": "/path/to/data"}
# def simple_handler(context):
#     return {"processed_count": len(context['input_file'])}
# step = WorkflowStep("read_data", simple_handler)
# definition = WorkflowDefinition("test", {})
# definition.add_step(step)
# engine = WorkflowEngine(context)
# final_context = engine.run_workflow(definition)