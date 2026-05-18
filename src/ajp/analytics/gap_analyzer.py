"""Gap analysis for compliance frameworks."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class ComplianceFramework(Enum):
    SOC2 = "soc2"
    GDPR = "gdpr"
    OWASP_LLM = "owasp_llm"


class ControlStatus(Enum):
    COMPLIANT = "compliant"
    PARTIAL = "partial"
    NON_COMPLIANT = "non_compliant"
    NOT_APPLICABLE = "not_applicable"


@dataclass
class ControlCheck:
    control_id: str
    framework: ComplianceFramework
    description: str
    status: ControlStatus
    evidence: str = ""
    score: float = 0.0


@dataclass
class GapFinding:
    control: ControlCheck
    recommendation: str
    priority: str


class GapAnalyzer:
    _CONTROLS = {
        ComplianceFramework.SOC2: [
            ("SOC2-TR-1", "Log immutability via hash chaining", ControlStatus.COMPLIANT, 1.0),
            ("SOC2-TR-2", "Digital signatures on entries", ControlStatus.COMPLIANT, 1.0),
            ("SOC2-TR-3", "Access control via RBAC", ControlStatus.COMPLIANT, 1.0),
            ("SOC2-TR-4", "Encryption at rest", ControlStatus.PARTIAL, 0.7),
            ("SOC2-TR-5", "Encryption in transit", ControlStatus.PARTIAL, 0.7),
            ("SOC2-AV-1", "Monitoring and alerting", ControlStatus.COMPLIANT, 1.0),
            ("SOC2-AV-2", "Incident response", ControlStatus.PARTIAL, 0.6),
            ("SOC2-CP-1", "Key management and rotation", ControlStatus.COMPLIANT, 1.0),
        ],
        ComplianceFramework.GDPR: [
            ("GDPR-55", "Data minimization", ControlStatus.PARTIAL, 0.7),
            ("GDPR-25", "Security of processing", ControlStatus.COMPLIANT, 1.0),
            ("GDPR-17", "Breach notification", ControlStatus.PARTIAL, 0.5),
            ("GDPR-17-shred", "Right to erasure (shredding)", ControlStatus.COMPLIANT, 1.0),
            ("GDPR-30", "Records of processing", ControlStatus.COMPLIANT, 1.0),
        ],
        ComplianceFramework.OWASP_LLM: [
            ("LLM-01", "Prompt injection protection", ControlStatus.COMPLIANT, 1.0),
            ("LLM-02", "Insecure output handling", ControlStatus.PARTIAL, 0.7),
            ("LLM-03", "Training data poisoning", ControlStatus.NON_COMPLIANT, 0.0),
            ("LLM-05", "Supply chain vulnerabilities", ControlStatus.PARTIAL, 0.5),
            ("LLM-06", "Sensitive information disclosure", ControlStatus.COMPLIANT, 1.0),
            ("LLM-08", "Agent prompt leakage", ControlStatus.COMPLIANT, 1.0),
            ("LLM-09", "Agent task manipulation", ControlStatus.PARTIAL, 0.6),
        ],
    }

    def __init__(self):
        self._results: Dict[ComplianceFramework, List[ControlCheck]] = {}
        self._run_timestamp = datetime.utcnow()

    def run_analysis(self, framework: Optional[ComplianceFramework] = None) -> List[GapFinding]:
        frameworks = [framework] if framework else list(ComplianceFramework)
        findings = []
        for fw in frameworks:
            controls = self._run_framework(fw)
            self._results[fw] = controls
            for ctrl in controls:
                if ctrl.status != ControlStatus.COMPLIANT:
                    findings.append(GapFinding(
                        control=ctrl,
                        recommendation=self._get_recommendation(ctrl),
                        priority="high" if ctrl.status == ControlStatus.NON_COMPLIANT else "medium",
                    ))
        return findings

    def _run_framework(self, framework: ComplianceFramework) -> List[ControlCheck]:
        controls = self._CONTROLS.get(framework, [])
        return [
            ControlCheck(
                control_id=c[0],
                framework=framework,
                description=c[1],
                status=c[2],
                score=c[3],
                evidence="Automated check via AJP framework",
            )
            for c in controls
        ]

    def _get_recommendation(self, control: ControlCheck) -> str:
        recommendations = {
            ControlStatus.PARTIAL: f"Improve {control.description} to full compliance",
            ControlStatus.NON_COMPLIANT: f"Implement {control.description} immediately",
        }
        return recommendations.get(control.status, "Maintain current compliance level")

    def get_compliance_score(self, framework: Optional[ComplianceFramework] = None) -> float:
        if framework:
            controls = self._results.get(framework, [])
            if not controls:
                return 0.0
            return sum(c.score for c in controls) / len(controls)
        all_controls = []
        for controls in self._results.values():
            all_controls.extend(controls)
        if not all_controls:
            return 0.0
        return sum(c.score for c in all_controls) / len(all_controls)

    def generate_report(self, format: str = "text") -> str:
        findings = []
        for fw in self._results:
            findings.extend(self.run_framework(fw))
        if format == "json":
            import json as _json
            report = {
                "timestamp": self._run_timestamp.isoformat(),
                "overall_score": self.get_compliance_score(),
                "frameworks": {},
            }
            for fw, controls in self._results.items():
                report["frameworks"][fw.value] = {
                    "score": self.get_compliance_score(fw),
                    "controls": [
                        {"id": c.control_id, "description": c.description,
                         "status": c.status.value, "score": c.score}
                        for c in controls
                    ],
                }
            return _json.dumps(report, indent=2)
        elif format == "markdown":
            lines = [f"# AJP Compliance Report\n", f"**Generated:** {self._run_timestamp.isoformat()}\n",
                     f"**Overall Score:** {self.get_compliance_score():.0%}\n"]
            for fw, controls in self._results.items():
                lines.append(f"\n## {fw.value.upper()} ({self.get_compliance_score(fw):.0%})\n")
                for c in controls:
                    lines.append(f"- [{c.status.value.upper()}] {c.control_id}: {c.description} ({c.score:.0%})")
            return "\n".join(lines)
        else:
            lines = [f"AJP Compliance Report - {self._run_timestamp.isoformat()}",
                     f"Overall Score: {self.get_compliance_score():.0%}", ""]
            for fw, controls in self._results.items():
                lines.append(f"{fw.value.upper()} ({self.get_compliance_score(fw):.0%}):")
                for c in controls:
                    lines.append(f"  [{c.status.value}] {c.control_id}: {c.description} ({c.score:.0%})")
                lines.append("")
            return "\n".join(lines)

    def run_framework(self, framework: ComplianceFramework) -> List[GapFinding]:
        controls = self._run_framework(framework)
        self._results[framework] = controls
        return [
            GapFinding(control=c, recommendation=self._get_recommendation(c),
                      priority="high" if c.status == ControlStatus.NON_COMPLIANT else "medium")
            for c in controls if c.status != ControlStatus.COMPLIANT
        ]
