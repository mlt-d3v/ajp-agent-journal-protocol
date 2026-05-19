        print(f"[AJP-JC] JournalChain '{journal_id}' initialized. Ready to append entries.")

    def append_action(self, 
                      action_type: str, 
                      action_payload: Dict[str, Any], 
                      is_critical: bool = False) -> bool:
        """
        The primary method to log an event. This function enforces 
        the entire AJP flow: Sanitization -> Validation -> Logging.
        
        :param action_type: e.g., 'TASK_START', 'TOOL_OUTPUT', 'TASK_FAILED'
        :param action_payload: The raw data payload from the agent's action.
        :param is_critical: Whether this action requires Vault/credential checks.
        :return: True if logged successfully, False otherwise.
        """
        print(f"\n[AJP-JC] Attempting to log event: {action_type}")
        
        # --- STEP 1: SANITIZATION (Data Retention) ---
        sanitized_payload = self.drm.mask_pii(action_payload)
        print(f"[AJP-JC] Payload successfully sanitized for PII.")
        
        # --- STEP 2: VALIDATION & SECURITY CHECK ---
        credential_required = False
        if is_critical:
            # Simulate check: If the action requires a critical resource, ensure the secret exists.
            try:
                # We check for a placeholder key defined in the original payload
                placeholder_key = action_payload.get("required_secret_key", "nonexistent_key")
                if placeholder_key != "nonexistent_key":
                    retrieved_secret = self.sm.retrieve_secret(f"{self.journal_id}-{placeholder_key}")
                     if not retrieved_secret:
                         print("[AJP-CUR] WARNING: Critical action requires secret, but none was found to validate. Proceeding with warning.")
                         credential_required = True
                     else:
                         print("[AJP-CUR] SUCCESS: Critical action verified against stored secret.")
                         credential_required = False
                else:
                    print("[AJP-CUR] INFO: Action did not require critical secrets check.")
            except Exception as e:
                print(f"[AJP-CUR] ERROR: Failed security check: {e}")
                return False

        # --- STEP 3: WORKFLOW LOGGING & COMMIT ---
        try:
            # Simulate the structured workflow definition creation
            definition = WorkflowDefinition(name=f"{action_type}_workflow", initial_context=self.current_state)
            
            # Simulate adding a step based on the action type
            step_handler_mock = lambda context: {**context, "last_action": action_type, "payload": sanitized_payload}
            step = WorkflowStep("log_event", step_handler_mock)
            definition.add_step(step)
            
            # Running the workflow simulation updates the internal context state
            self.workflow_engine.register_workflow(definition)
            self.workflow_engine.run_workflow(definition)
            
            # Update the internal state with the final, logged context
            self.current_state = self.workflow_engine.context.copy()
            
            # --- SUCCESS: Final Audit Log ---
            print("\n==========================================================================")
            print(f"✅ AUDIT SUCCESS: Journal '{self.journal_id}' commit successful.")
            print(f"   Event: {action_type} | Timestamp: {datetime.now().isoformat()}")
            print(f"   Final State Hash (Abbreviated): {hash(str(self.current_state)) % 1000}")
            print("========================================================================")
            return True
            
        except Exception as e:
            print(f"❌ JOURNAL FATAL ERROR: Could not finalize journal entry due to internal system failure: {e}")
            return False

class JournalChain:
    """
    Implements the core functionality of the Agent Journal Protocol.
    Manages the immutable, time-stamped record of agent activities.
    """
    
    def __init__(self, journal_id: str, initial_context: Dict[str, Any]):
        self.journal_id = journal_id
        self.context_history: List[Dict[str, Any]] = []
        self.workflow_engine = WorkflowEngine(initial_context)
        
        # 1. Initialize required sub-systems (Dependency Injection)
        self.drm = DataRetentionManager()
        self.sm = SecretManager()
        self.current_state = initial_context.copy()

        print(f"[AJP-JC] JournalChain '{journal_id}' initialized. Ready to append entries.")

    def append_action(self, 
                      action_type: str, 
                      action_payload: Dict[str, Any], 
                      is_critical: bool = False) -> bool:
        """
        The primary method to log an event. This function enforces 
        the entire AJP flow: Sanitization -> Validation -> Logging.
        
        :param action_type: e.g., 'TASK_START', 'TOOL_OUTPUT', 'TASK_FAILED'
        :param action_payload: The raw data payload from the agent's action.
        :param is_critical: Whether this action requires Vault/credential checks.
        :return: True if logged successfully, False otherwise.
        """
        print(f"\n[AJP-JC] Attempting to log event: {action_type}")
        
        # --- STEP 1: SANITIZATION (Data Retention) ---
        sanitized_payload = self.drm.mask_pii(action_payload)
        print(f"[AJP-JC] Payload successfully sanitized for PII.")
        
        # --- STEP 2: VALIDATION & SECURITY CHECK ---
        credential_required = False
        if is_critical:
            # Simulate check: If the action requires a critical resource, ensure the secret exists.
            try:
                # We check for a placeholder key defined in the original payload
                placeholder_key = action_payload.get("required_secret_key", "nonexistent_key")
                if placeholder_key != "nonexistent_key":
                    retrieved_secret = self.sm.retrieve_secret(f"{self.journal_id}-{placeholder_key}")
                     if not retrieved_secret:
                         print("[AJP-CUR] WARNING: Critical action requires secret, but none was found to validate. Proceeding with warning.")
                         credential_required = True
                     else:
                         print("[AJP-CUR] SUCCESS: Critical action verified against stored secret.")
                         credential_required = False
                else:
                    print("[AJP-CUR] INFO: Action did not require critical secrets check.")
            except Exception as e:
                print(f"[AJP-CUR] ERROR: Failed security check: {e}")
                return False

        # --- STEP 3: WORKFLOW LOGGING & COMMIT ---
        try:
            # Simulate the structured workflow definition creation
            definition = WorkflowDefinition(name=f"{action_type}_workflow", initial_context=self.current_state)
            
            # Simulate adding a step based on the action type
            step_handler_mock = lambda context: {**context, "last_action": action_type, "payload": sanitized_payload}

            step = WorkflowStep("log_event", step_handler_mock)
            definition.add_step(step)
            
            # Running the workflow simulation updates the internal context state
            self.workflow_engine.register_workflow(definition)
            self.workflow_engine.run_workflow(definition)
            
            # Update the internal state with the final, logged context
            self.current_state = self.workflow_engine.context.copy()
            
            # --- SUCCESS: Final Audit Log ---
            print("\n==========================================================================")
            print(f"✅ AUDIT SUCCESS: Journal '{self.journal_id}' commit successful.")
            print(f"   Event: {action_type} | Timestamp: {datetime.now().isoformat()}")
            print(f"   Final State Hash (Abbreviated): {hash(str(self.current_state)) % 1000}")
            print("==========================================================================")
            return True
            
        except Exception as e:
            print(f"❌ JOURNAL FATAL ERROR: Could not finalize journal entry due to internal system failure: {e}")
            return False

# Example usage (for testing):
# # 1. Initialize the Journal
# journal = JournalChain("user-michaelthomas-session", {"user_role": "dev", "project": "hermes-agent"})
# # 2. Simulate a starting event
# journal.append_action("SESSION_START", {"user_id": "u123", "ip": "1.2.3.4", "required_secret_key": None})
# # 3. Simulate a failure event (which triggers the workflow engine failure path)
# journal.append_action("TASK_FAIL", {"component": "API_GATEWAY", "error": "Rate limit exceeded", "required_secret_key": "RATE_LIMIT_KEY"}, is_critical=True)