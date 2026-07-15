---
name: siteagent-accessibility
description: Apply WCAG 2.2 AA-oriented requirements to static output.
---
# Accessibility
Inputs: builder context and rendered DOM. Outputs: accessibility contract and findings.
Rules: semantic structure, language, labels, keyboard focus, contrast, reduced motion and meaningful alt text. Prohibited: focus removal, image-only actions and decorative alt text presented as proof.
Failure conditions: critical keyboard, contrast, name/role/value or viewport issue. Checklist: headings, landmarks, controls and media are checked. Done when no high/critical finding remains.
