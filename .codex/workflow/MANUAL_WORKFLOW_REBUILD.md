# SiteAgent — rebuild around the proven ChatGPT → Codex workflow

Act as `$siteagent-project-director`.

## Product correction

Stop polishing Harbour Dental. It already proved that visual diversity alone is not enough.

The current Creative Studio architecture is solving the wrong problem. It tries to research, invent, build, and self-grade a site from sparse structured evidence in one automated loop. The proven human workflow is:

1. Start with one Instagram business URL.
2. Research the business deeply:
   - exact services/products;
   - target audience;
   - business and price level;
   - language/location;
   - customer intent;
   - positioning;
   - verified facts;
   - unknowns;
   - prohibited claims.
3. Produce a rich business/brand summary.
4. In a separate creative-director stage, invent:
   - site concept;
   - structure;
   - storytelling;
   - visual system;
   - typography;
   - palette;
   - composition;
   - CTA logic;
   - responsive behavior.
5. Prepare real Instagram media:
   - crop Instagram UI;
   - deduplicate;
   - classify;
   - choose hero/gallery/detail assets;
   - upload approved assets to Cloudinary;
   - persist URLs and provenance.
6. Give Codex one dense implementation package:
   - business research;
   - design brief;
   - real media;
   - selected references;
   - acceptance contract.
7. Codex implements, renders, critiques, materially revises, and hands off to the existing acceptance/Cloudflare/Telegram flow.

Automate this exact workflow. Do not replace it with category templates, deterministic page compositions, synthetic fixtures, or self-rating systems.

## Why direct Codex performs better

Direct Codex receives:
- a rich prompt;
- curated real photos;
- explicit design direction;
- human-selected references;
- human quality control.

SiteAgent currently gives a thinner structured package and asks one automated loop to research, art-direct, build, and approve itself.

Separate the design-strategy plane from the Codex implementation plane.

Add provider/role separation, adapting names to the repository:

- `RESEARCH_STRATEGIST_PROVIDER`
- `DESIGN_DIRECTOR_PROVIDER`
- `SITE_BUILDER_PROVIDER=codex`

The design-director output must be a complete implementation brief, not a category, token set, or generic `SiteSpec`.

## Human-approved reference seed list

Persist normalized URLs without tracking parameters:

- https://optidigitalagent.github.io/eliz-de-fleur-site-20260711095843/
- http://belladentclinik.kr.ua/
- https://optidigitalagent.github.io/orange-beauty-studio/
- https://optidigitalagent.github.io/atmosfera-site/
- https://optidigitalagent.github.io/drivepark/
- https://optidigitalagent.github.io/yourdental1/
- https://optidigitalagent.github.io/yourdental2/
- https://optidigitalagent.github.io/hollywood2/
- https://optidigitalagent.github.io/hollywood1/
- https://optidigitalagent.github.io/kafespeka2/
- https://uniquerabbitstudios.com/
- https://optidigitalagent.github.io/kirkovsky/
- https://newartem855-netizen.github.io/-ZVD/
- https://defolixx.github.io/SunSity/
- https://optidigitalagent.github.io/hereta/
- https://optidigitalagent.github.io/orange2/
- https://optidigitalagent.github.io/orange1/
- https://optidigitalagent.github.io/dentistry_kievskaya2/
- https://optidigitalagent.github.io/dentistry_kievskaya1/
- https://newartem855-netizen.github.io/auratop1/
- https://newartem855-netizen.github.io/Panem-Digital-Agency/
- https://eurozet.ua/
- https://webgoalz.com/
- https://zaffiraxis.github.io/status1/
- https://zaffiraxis.github.io/silk-road-rent-car/index.html#why
- https://zaffiraxis.github.io/margo-salon/
- https://iodent.dental/
- https://parkrestaurant.kyiv.ua/

## Reference-library rule

References teach range and quality. They are not category templates.

For each reference, capture and store:

- normalized URL;
- title;
- desktop screenshot;
- mobile screenshot;
- business/product context;
- audience and conversion goal;
- first-viewport logic;
- information architecture;
- storytelling;
- composition/grid/spacing;
- typography;
- palette and contrast;
- media treatment;
- motion/interaction;
- CTA strategy;
- mobile behavior;
- what to learn;
- what must not be copied;
- reusable trait tags.

Select references for new jobs by traits across categories.

Example: a dental site may borrow calm hierarchy from hospitality, proof structure from professional services, and gallery rhythm from architecture. It must not receive a “dental template.”

## Required implementation

### 1. Reference importer

Create a resumable local command, e.g.:

```powershell
python -m site_agent.reference_import
```

It must:

- read the seed list;
- open each URL with the existing local browser runtime;
- capture desktop/mobile full-page screenshots;
- record failures without aborting the whole import;
- extract a structural and visual summary;
- create `references/site_designs/<id>/reference.json`;
- update a searchable catalog/index;
- never modify or publish reference sites.

### 2. Media-preparation stage

Before design:

- accept Instagram post screenshots and downloaded media;
- automatically crop Instagram UI while preserving the actual photo/video frame;
- deduplicate;
- score image quality;
- classify orientation and use cases;
- select hero/gallery/detail candidates;
- upload approved assets to Cloudinary;
- persist Cloudinary URLs and provenance;
- never represent fixture/stock media as client work.

### 3. Research Strategist

Create a rich cited business brief:

- exact product identity;
- services/products;
- target audience and buying context;
- business/price level;
- location/language;
- positioning and differentiators;
- customer questions and objections;
- trust signals;
- brand/media signals;
- unknowns and forbidden claims;
- recommended site scope.

### 4. Design Director

Use the business brief, media manifest, and 3–6 trait-relevant references.

Produce a detailed `design_implementation_brief.md` containing:

- central creative idea;
- exact page structure;
- narrative/storytelling;
- first viewport;
- typography;
- palette;
- spacing;
- grid;
- media treatment;
- motion;
- CTA/conversion logic;
- desktop/tablet/mobile behavior;
- copy direction;
- section-level requirements;
- explicit anti-patterns;
- rationale for selected references;
- what must not be copied.

Do not generate three concepts as a ritual. Create multiple concepts only when the business genuinely benefits from comparison.

### 5. Codex implementation

Explicitly invoke `$siteagent-web-studio`.

Codex receives the complete implementation package and writes the actual site. It must implement the approved brief rather than reinterpret it into a generic template.

Browser screenshots, independent criticism, and material revision remain mandatory.

### 6. Simplify the current pipeline

Audit and deprecate machinery that exists mainly to compensate for weak inputs or force synthetic diversity.

Keep deterministic systems that genuinely help:

- evidence integrity;
- product/scope gates;
- media provenance;
- browser QA;
- accessibility;
- recovery;
- publishing;
- Telegram delivery.

Do not break Telegram, queue, recovery, Cloudflare, or receipts.

## Acceptance

Before production rollout:

1. Import and analyze the entire reference list.
2. Demonstrate the exact manual-equivalent pipeline on two rich controlled businesses with materially different media and positioning.
3. Show:
   - research brief;
   - design implementation brief;
   - selected references and reasons;
   - Cloudinary media manifest;
   - final Codex implementation package;
   - desktop/mobile screenshots;
   - critic/fixer history.
4. Prove the results are not copies of references or each other.
5. Keep human calibration enabled.
6. Do not run `go`, Telegram, or Cloudflare during this remediation.

## Final handoff

Commit and push valid changes.

Stop at a human calibration package that shows the complete end-to-end creative workflow, not another synthetic category fixture.
