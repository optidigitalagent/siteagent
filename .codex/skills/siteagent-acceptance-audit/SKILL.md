---
name: siteagent-acceptance-audit
description: Aggregate evidence, contracts and critic results into a deploy decision.
---
# Acceptance audit
Inputs: all required artifacts, critic council, technical gate and built site. Outputs: category scores, floors, blockers, reviewed artifacts and deploy decision.
Rules: every category floor and no-critical/high rule is mandatory; technical score cannot compensate business/design failure. Prohibited: publishing on absent artifacts or downgrading unresolved issues.
Failure conditions: insufficient evidence, invalid schema, missing viewport, failed floor, failed technical gate or missing index. Checklist: schema version, contracts, reports and artifact paths are recorded. Done only when deployment is explicitly allowed or blocked with reasons.
