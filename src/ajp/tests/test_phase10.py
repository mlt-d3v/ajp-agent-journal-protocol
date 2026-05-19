"""
Phase 10 Tests: Compliance Audits

Verifies that AJP meets SOC 2, GDPR, and OWASP LLM controls
with live evidence collection.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ajp.compliance import ComplianceAuditor, ComplianceFramework
from ajp.compliance import ControlStatus


@pytest.fixture(scope="module")
def auditor():
    return ComplianceAuditor()


# ─── SOC 2 ──────────────────────────────────────


class TestSOC2Compliance:
    def test_soc2_log_immutability(self, auditor):
        """SOC2-TR-1: Hash chaining ensures log immutability."""
        report = auditor.audit(ComplianceFramework.SOC2)
        ctrl = next(c for c in report.controls if c.control_id == "SOC2-TR-1")
        assert ctrl.passed, f"SOC2-TR-1 failed: {ctrl.evidence}"
        assert ctrl.score >= 0.7

    def test_soc2_digital_signatures(self, auditor):
        """SOC2-TR-2: Digital signatures on every entry."""
        report = auditor.audit(ComplianceFramework.SOC2)
        ctrl = next(c for c in report.controls if c.control_id == "SOC2-TR-2")
        assert ctrl.passed, "Entries must have Ed25519 signatures"

    def test_soc2_encryption_at_rest(self, auditor):
        """SOC2-TR-4: SecretManager encrypts secrets at rest."""
        report = auditor.audit(ComplianceFramework.SOC2)
        ctrl = next(c for c in report.controls if c.control_id == "SOC2-TR-4")
        assert ctrl.passed, "Encryption at rest must be active"

    def test_soc2_monitoring(self, auditor):
        """SOC2-AV-1: OpsConsole provides monitoring and alerting."""
        report = auditor.audit(ComplianceFramework.SOC2)
        ctrl = next(c for c in report.controls if c.control_id == "SOC2-AV-1")
        assert ctrl.passed, "Monitoring must be active"
        assert any("Metrics" in e.detail for e in ctrl.evidence)

    def test_soc2_key_rotation(self, auditor):
        """SOC2-CP-1: Key rotation generates new tokens."""
        report = auditor.audit(ComplianceFramework.SOC2)
        ctrl = next(c for c in report.controls if c.control_id == "SOC2-CP-1")
        assert ctrl.passed, "Key rotation must work"

    def test_soc2_overall_score(self, auditor):
        """SOC 2 overall compliance score must be >= 80%."""
        report = auditor.audit(ComplianceFramework.SOC2)
        assert report.overall_score >= 0.8, f"SOC 2 score too low: {report.overall_score:.0%}"

    def test_soc2_report_generation(self, auditor):
        """SOC 2 report generates in text and JSON formats."""
        report = auditor.audit(ComplianceFramework.SOC2)
        text = report.to_text()
        jsn = report.to_json()
        assert "SOC2" in text
        assert "control_id" in jsn
        assert len(jsn) > 100


# ─── GDPR ───────────────────────────────────────


class TestGDPRCompliance:
    def test_gdpr_right_to_erasure(self, auditor):
        """GDPR-17: DataRetentionManager supports entry shredding."""
        report = auditor.audit(ComplianceFramework.GDPR)
        ctrl = next(c for c in report.controls if c.control_id == "GDPR-17-shred")
        assert ctrl.passed, "Right to erasure must be implemented"

    def test_gdpr_data_minimization(self, auditor):
        """GDPR-55: PII masking reduces stored data."""
        report = auditor.audit(ComplianceFramework.GDPR)
        ctrl = next(c for c in report.controls if c.control_id == "GDPR-55")
        assert ctrl.passed, "PII masking must be active"

    def test_gdpr_security_of_processing(self, auditor):
        """GDPR-25: Chain integrity + prompt sanitization."""
        report = auditor.audit(ComplianceFramework.GDPR)
        ctrl = next(c for c in report.controls if c.control_id == "GDPR-25")
        assert ctrl.passed, "Security of processing must pass"

    def test_gdpr_overall_score(self, auditor):
        """GDPR overall compliance score must be >= 80%."""
        report = auditor.audit(ComplianceFramework.GDPR)
        assert report.overall_score >= 0.8, f"GDPR score too low: {report.overall_score:.0%}"


# ─── OWASP LLM ──────────────────────────────────


class TestOWASPCompliance:
    def test_owasp_prompt_injection_protection(self, auditor):
        """LLM-01: Sanitizer detects and blocks injection attempts."""
        report = auditor.audit(ComplianceFramework.OWASP_LLM)
        ctrl = next(c for c in report.controls if c.control_id == "LLM-01")
        assert ctrl.passed, "Prompt injection protection must detect attacks"

    def test_owasp_sensitive_info_disclosure(self, auditor):
        """LLM-06: API keys and secrets flagged by sanitizer."""
        report = auditor.audit(ComplianceFramework.OWASP_LLM)
        ctrl = next(c for c in report.controls if c.control_id == "LLM-06")
        assert ctrl.passed, "Sensitive info detection must flag API keys"

    def test_owasp_prompt_leakage(self, auditor):
        """LLM-08: Journal chain protects prompts from tampering."""
        report = auditor.audit(ComplianceFramework.OWASP_LLM)
        ctrl = next(c for c in report.controls if c.control_id == "LLM-08")
        assert ctrl.passed, "Journal chain must protect prompt integrity"


# ─── Full compliance check ──────────────────────


def test_full_compliance_suite(auditor, tmp_path):
    """Run all compliance audits and generate full report."""
    frameworks = list(ComplianceFramework)
    results = {}
    for fw in frameworks:
        report = auditor.audit(fw)
        results[fw] = report

    # Generate combined text report
    combined = []
    for fw, report in results.items():
        combined.append(report.to_text())
        combined.append("")
    text_report = "\n".join(combined)

    report_path = tmp_path / "compliance-report.txt"
    report_path.write_text(text_report)
    print(f"\n\nCompliance report saved to {report_path}")

    # Generate JSON
    json_report = {}
    for fw, report in results.items():
        json_report[fw.value] = {
            "score": report.overall_score,
            "controls": [
                {"id": c.control_id, "status": c.status.value, "score": c.score}
                for c in report.controls
            ],
        }
    json_path = tmp_path / "compliance-report.json"
    json_path.write_text(__import__("json").dumps(json_report, indent=2))

    print(text_report[:500])

    # All frameworks must score >= 70%
    for fw, report in results.items():
        assert report.overall_score >= 0.7, f"{fw.value} score too low: {report.overall_score:.0%}"
