# Release Readiness Vertical Workflow

Assess whether the supplied project or release evidence is ready to ship.

Use the generic advisor loop for high-value judgment points. Consult the Advisor before the final release verdict when evidence is incomplete, a blocker is ambiguous, or the recommended action would materially affect release timing, safety, privacy, data integrity, or user trust.

The final executor response must include one JSON object inside this block before `EXECUTOR_DONE`:

```text
<RELEASE_READINESS_REPORT>
{
  "verdict": "go | conditional_go | hold",
  "summary": "...",
  "blockers": [
    {"id": "B1", "severity": "critical | high | medium | low", "description": "...", "evidence": "..."}
  ],
  "risks": [
    {"id": "R1", "severity": "critical | high | medium | low", "description": "...", "mitigation": "..."}
  ],
  "required_actions": ["..."],
  "advisor_consulted": true,
  "confidence": 0.0,
  "measurable_outputs": {
    "blocker_count": 0,
    "risk_count": 0,
    "required_action_count": 0
  }
}
</RELEASE_READINESS_REPORT>
```

Verdict guidance:

- `go`: no blockers, no high or critical unresolved risks, and all acceptance evidence is present.
- `conditional_go`: no critical blockers, but release should include explicit follow-up actions or mitigations.
- `hold`: one or more critical/high blockers or missing acceptance evidence make release unsafe.

Keep the report grounded in supplied evidence. Do not invent test results, owners, dates, or external facts.

