# Product Vision

SiteAgent should behave like a strong small web studio whose team understands
business, brand, copy, UX, visual design, frontend engineering, QA, deployment,
and recovery.

The product is not successful when it merely produces valid HTML. It is
successful when a visitor can understand the business, feel a deliberate brand
experience, trust the offer, and take the intended action.

## What SiteAgent must become

- Evidence-grounded: facts, claims, language, product, and media usage are traceable.
- Bespoke: composition comes from this business, not its category.
- Commercial: the page helps a real customer understand and act.
- Visually directed: typography, layout, media, motion, and signature elements form
  one coherent idea.
- Responsive by design: mobile is an intentional composition, not a shrunken desktop.
- Self-critical: separate critics challenge the work and force material revision.
- Recoverable: interruptions resume from durable checkpoints.
- Quiet in production: the user receives only the final verified public link.

## Design diversity

A restaurant may be cinematic, editorial, utilitarian, playful, local, luxurious,
or product-led. A school may be warm, rigorous, platform-led, community-led, or
outcome-led. Category is context, not a template selector.

Shared technical primitives are acceptable. Shared page composition, visual
language, narrative, and copy are not.

## Project revision lifecycle

SiteAgent must eventually support a separate `SiteRevisionAgent` for an existing
accepted project. It receives a normal-language change request, loads the saved
business and design context, edits the current site instead of regenerating it,
runs tests and visual QA, and publishes a new isolated preview. Customer
production changes remain a later, explicit human-approved action. This
revision workflow must stay separate from new-site generation.
