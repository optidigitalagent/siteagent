---
name: siteagent-anti-template-critic
description: Detect unjustified repetition of layout, sections, tokens and copy.
---
# Anti-template critic
Inputs: selected direction, current fingerprint and bounded historical fingerprints. Outputs: similarity report and issues.
Rules: permit token-driven primitive reuse; require a business reason for structure reuse. Prohibited: comparing raw media URLs or using unstable random values.
Failure conditions: a full-layout match across distinct businesses or missing current fingerprint. Checklist: structure, CTA, narrative, palette and phrase overlap are compared. Done when report is persisted.
