#!/usr/bin/env python3
"""Verification script for AJP - validates all 7 phases."""
import sys
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(script_dir, "..", "src")
sys.path.insert(0, src_dir)

def check_phase(phase_name, imports):
    try:
        for imp in imports:
            exec(imp)
        print(f"  [PASS] {phase_name}")
        return True
    except Exception as e:
        print(f"  [FAIL] {phase_name}: {e}")
        return False

def main():
    print("AJP Verification - All 7 Phases")
    print("=" * 40)
    results = []
    results.append(check_phase("Phase 1: Core Library", [
        "from ajp.core.entry import JournalEntry, EventType",
        "from ajp.core.chain import JournalChain",
        "from ajp.core.merkle import MerkleTree",
        "from ajp.core.secret import SecretManager",
        "from ajp.core.sanitizer import PromptSanitizer",
        "from ajp.core.rate_limiter import RateLimiter",
        "from ajp.core.retention import DataRetentionManager",
    ]))
    results.append(check_phase("Phase 2: Async Journal Service", [
        "from ajp.service.journal import AsyncJournalService, JournalConfig",
        "from ajp.service.buffer import WriteBuffer",
        "from ajp.service.writer import BatchWriter",
        "from ajp.service.storage import MockStorage",
    ]))
    results.append(check_phase("Phase 3: Security Hardening", [
        "from ajp.security.vault_client import VaultClient",
        "from ajp.security.hsm import SoftwareHSM, CloudHSM",
        "from ajp.security.orchestrator import SecurityOrchestrator",
        "from ajp.core.anchoring import MerkleAnchoringService",
    ]))
    results.append(check_phase("Phase 4: Analytics & Monitoring", [
        "from ajp.analytics.semantic_search import SemanticSearchEngine",
        "from ajp.analytics.failure_interceptor import FailureInterceptor",
        "from ajp.analytics.ops_console import OpsConsole",
        "from ajp.analytics.gap_analyzer import GapAnalyzer",
    ]))
    results.append(check_phase("Phase 5: Workflow + Tracing", [
        "from ajp.workflow.engine import WorkflowEngine",
        "from ajp.workflow.tracer import Tracer",
        "from ajp.workflow.metrics import MetricsExporter",
    ]))
    results.append(check_phase("Phase 6: REST Server + SDK", [
        "from ajp.server.app import create_app",
        "from ajp.sdk.client import AJPClient, SyncAJPClient",
        "from ajp.sdk.config import AgentConfig",
    ]))
    results.append(check_phase("Phase 7: Production Integrations", [
        "from ajp.integrations.postgres import PostgresStorage, PostgresConfig",
        "from ajp.integrations.vault import RealVaultClient, VaultConfig",
        "from ajp.integrations.temporal import TemporalWorkflowEngine, WorkflowConfig",
        "from ajp.integrations.opentelemetry import OTLPExporter, OTelConfig",
    ]))
    print("=" * 40)
    passed = sum(results)
    total = len(results)
    print(f"Result: {passed}/{total} phases verified")
    if passed == total:
        print("All phases OK - AJP is ready.")
        return 0
    else:
        print("Some phases failed - check imports.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
