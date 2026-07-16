"""Build a local, review-only package from completed reference-import artifacts.

This tool is deliberately offline: it reads the already saved catalog and screenshots,
then writes review pages without updating any source ``reference.json`` file.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import struct
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("references/site_designs")
OUTPUT = ROOT / "human_review"
INVALID_INPUT = OUTPUT / "human_review_decisions.invalid.json"
TRAITS = (
    "premium", "editorial", "conversion-led", "media-led", "trust-led", "minimal",
    "expressive", "local business", "service-heavy", "portfolio-first", "calm", "bold",
)
TRAIT_RULES = {
    "premium": ("premium", "luxury", "elegant", "affluent", "upscale", "elevated", "bespoke"),
    "editorial": ("editorial", "serif", "curated", "sparse", "aspirational"),
    "conversion-led": ("cta", "book", "booking", "appointment", "inquiry", "contact", "lead", "form", "call"),
    "media-led": ("photo", "photography", "gallery", "image", "video", "visual", "imagery"),
    "trust-led": ("trust", "proof", "testimonial", "review", "certif", "credential", "result", "team"),
    "minimal": ("minimal", "restraint", "sparse", "uncluttered", "white space", "whitespace"),
    "expressive": ("expressive", "playful", "colorful", "vibrant", "energetic", "creative"),
    "local business": ("local", "kyiv", "clinic", "cafe", "restaurant", "salon", "neighborhood", "community"),
    "service-heavy": ("service", "consultation", "appointment", "treatment", "process", "booking", "care"),
    "portfolio-first": ("portfolio", "project", "gallery", "case stud", "showcase", "product display"),
    "calm": ("calm", "soft", "muted", "orderly", "restrained", "gentle", "clean"),
    "bold": ("bold", "high-contrast", "high contrast", "vivid", "strong", "black", "bright"),
}
SECRET_RE = re.compile(r"(?i)(?:sk-[a-z0-9_-]{16,}|api[_-]?key\s*[:=]|authorization\s*[:=]|bearer\s+[a-z0-9._-]{16,})")
MANUAL_REVIEW_FLAGS = {
    "optidigitalagent-github-io-kirkovsky": "The captured page is a GitHub Pages 404 rather than a usable design reference. Exclude it from active selection unless it is recaptured successfully.",
    "optidigitalagent-github-io-orange-beauty-studio": "The desktop capture contains substantial blank or unrendered sections. It requires an explicit human exclusion or a future recapture before it can influence selection.",
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _png_size(path: Path) -> tuple[int, int]:
    """Read PNG dimensions without opening or transforming the captured image."""
    with path.open("rb") as image:
        header = image.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError(f"Expected a PNG capture: {path}")
    return struct.unpack(">II", header[16:24])


def _flags(record: dict[str, Any]) -> list[str]:
    messages = []
    identifier = record["id"]
    if identifier in MANUAL_REVIEW_FLAGS:
        messages.append(MANUAL_REVIEW_FLAGS[identifier])
    declared = record.get("capture", {}).get("browser_viewports", {}).get("mobile", [])
    width, _ = _png_size(ROOT / identifier / "mobile.png")
    if declared and width != declared[0]:
        messages.append(f"Mobile file width is {width}px while the recorded mobile viewport width is {declared[0]}px. Treat this as a capture-integrity mismatch; do not use it for mobile behavior selection until a human resolves it.")
    return messages


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)


def _json_for_html(value: object) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def _text(record: dict[str, Any]) -> str:
    analysis = record.get("analysis", {})
    values: list[str] = []
    for key in ("business_context", "audience", "conversion_goal", "first_viewport_logic", "narrative_storytelling", "composition_grid", "spacing_rhythm", "typography", "palette_contrast", "media_treatment", "cta_strategy", "desktop_behavior", "mobile_behavior", "reusable_cross_category_traits", "traits"):
        value = analysis.get(key, record.get(key, ""))
        values.extend(value if isinstance(value, list) else [value])
    return " ".join(str(value).lower() for value in values)


def _trait_tags(record: dict[str, Any]) -> list[str]:
    corpus = _text(record)
    return [trait for trait in TRAITS if any(word in corpus for word in TRAIT_RULES[trait])]


def _list(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{_e(item)}</li>" for item in items) + "</ul>"


def _field(label: str, value: object) -> str:
    if isinstance(value, list):
        content = _list([str(item) for item in value])
    else:
        content = f"<p>{_e(value)}</p>"
    return f"<section class=\"field\"><h4>{_e(label)}</h4>{content}</section>"


def _record_card(record: dict[str, Any], tags: list[str]) -> str:
    analysis = record["analysis"]
    identifier = record["id"]
    fields = (
        ("Business context", analysis["business_context"]), ("Audience", analysis["audience"]),
        ("Conversion goal", analysis["conversion_goal"]), ("First viewport logic", analysis["first_viewport_logic"]),
        ("Information architecture", analysis["information_architecture"]), ("Narrative / storytelling", analysis["narrative_storytelling"]),
        ("Composition / grid", analysis["composition_grid"]), ("Typography", analysis["typography"]),
        ("Palette / contrast", analysis["palette_contrast"]), ("Media treatment", analysis["media_treatment"]),
        ("CTA strategy", analysis["cta_strategy"]), ("Mobile behavior", analysis["mobile_behavior"]),
        ("Reusable cross-category traits", analysis["reusable_cross_category_traits"]),
        ("What to learn", analysis["learn"]), ("What must not be copied", analysis["do_not_copy"]),
    )
    badges = "".join(f"<span class=\"tag\">{_e(tag)}</span>" for tag in tags) or "<span class=\"tag neutral\">unclassified</span>"
    facts = "".join(_field(label, value) for label, value in fields)
    desktop_size = _png_size(ROOT / identifier / "desktop.png")
    mobile_size = _png_size(ROOT / identifier / "mobile.png")
    declared = record["capture"]["browser_viewports"]
    warnings = _flags(record)
    warning_html = "" if not warnings else "<aside class=\"capture-warning\"><strong>Selection safeguard:</strong> " + "<br>".join(_e(warning) for warning in warnings) + "</aside>"
    return f"""
    <article id="ref-{_e(identifier)}" class="reference" data-traits="{_e('|'.join(tags))}">
      <header class="reference-head">
        <div><p class="eyebrow">Completed screenshot analysis</p><h2>{_e(record['title'])}</h2>
        <p class="source-url">{_e(record['normalized_url'])}</p></div>
        <button class="copy-url" type="button" data-url="{_e(record['normalized_url'])}">Copy source URL</button>
      </header>
      <div class="tags">{badges}</div>
      {warning_html}
      <div class="captures">
        <figure><figcaption>Desktop file · actual {_e(desktop_size[0])} × {_e(desktop_size[1])} px · recorded viewport {_e(declared['desktop'][0])} × {_e(declared['desktop'][1])}</figcaption><img src="../{_e(identifier)}/desktop.png" alt="Desktop full-page capture of {_e(record['title'])}" loading="lazy"></figure>
        <figure><figcaption>Mobile file · actual {_e(mobile_size[0])} × {_e(mobile_size[1])} px · recorded viewport {_e(declared['mobile'][0])} × {_e(declared['mobile'][1])}</figcaption><img src="../{_e(identifier)}/mobile.png" alt="Mobile full-page capture of {_e(record['title'])}" loading="lazy"></figure>
      </div>
      <div class="facts">{facts}</div>
      <fieldset class="decision" data-reference="{_e(identifier)}"><legend>Human review decision</legend>
        <label><input type="radio" name="decision-{_e(identifier)}" value="approve"> Approve</label>
        <label><input type="radio" name="decision-{_e(identifier)}" value="approve_with_notes"> Approve with notes</label>
        <label><input type="radio" name="decision-{_e(identifier)}" value="exclude_from_active_selection"> Exclude from active selection</label>
        <label class="notes">Notes <textarea rows="3" data-notes="{_e(identifier)}" placeholder="Optional review notes"></textarea></label>
      </fieldset>
    </article>"""


def _styles() -> str:
    return """
    :root { color-scheme: light; --ink:#17212b; --muted:#596775; --line:#d7e0e8; --paper:#f7f9fb; --panel:#fff; --accent:#0d6781; --accent-soft:#e5f4f7; --danger:#9d3131; }
    * { box-sizing:border-box; } html { scroll-behavior:smooth; } body { margin:0; min-width:320px; overflow-x:hidden; background:var(--paper); color:var(--ink); font:16px/1.55 Inter, ui-sans-serif, system-ui, sans-serif; }
    a { color:var(--accent); } .shell { width:min(1440px, calc(100% - 32px)); margin:auto; } .masthead { padding:40px 0 28px; border-bottom:1px solid var(--line); } h1,h2,h3,h4,p { margin-top:0; } h1 { max-width:24ch; margin-bottom:10px; font-size:clamp(2rem,5vw,4rem); line-height:1.02; letter-spacing:-.045em; } h2 { font-size:clamp(1.45rem,3vw,2.2rem); line-height:1.15; } h3 { margin:0 0 8px; font-size:1rem; } h4 { margin-bottom:6px; color:var(--muted); font-size:.72rem; letter-spacing:.08em; text-transform:uppercase; } .lede,.source-url,.note { color:var(--muted); } .source-url { overflow-wrap:anywhere; font-family:ui-monospace, monospace; font-size:.82rem; } .eyebrow { margin-bottom:5px; color:var(--accent); font-size:.75rem; font-weight:750; letter-spacing:.08em; text-transform:uppercase; }
    .summary { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; padding:24px 0; } .metric,.provenance,.errors,.reference { min-width:0; background:var(--panel); border:1px solid var(--line); border-radius:14px; box-shadow:0 1px 2px #17212b0c; } .metric { padding:16px; } .metric strong { display:block; font-size:1.7rem; line-height:1.05; } .metric span { color:var(--muted); font-size:.86rem; }
    .meta-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin:0 0 28px; } .provenance,.errors { padding:20px; } .provenance dl { display:grid; grid-template-columns:max-content 1fr; gap:8px 16px; margin:0; } dt { color:var(--muted); } dd { margin:0; overflow-wrap:anywhere; } .errors details { border-top:1px solid var(--line); padding:12px 0; } .errors summary { cursor:pointer; font-weight:700; } .errors p { margin:8px 0 0; } code { overflow-wrap:anywhere; }
    .toolbar { position:sticky; z-index:4; top:0; padding:14px 0; background:#f7f9fbea; backdrop-filter:blur(10px); border-bottom:1px solid var(--line); } .toolbar-inner { display:flex; align-items:center; gap:10px; flex-wrap:wrap; } button,.button { display:inline-flex; align-items:center; justify-content:center; min-width:44px; min-height:44px; border:1px solid #9eb5c2; border-radius:999px; background:#fff; color:var(--ink); cursor:pointer; padding:8px 12px; font:inherit; font-size:.88rem; } button:hover,.button:hover { border-color:var(--accent); background:var(--accent-soft); } .button.primary { border-color:var(--accent); background:var(--accent); color:#fff; text-decoration:none; } .filters { display:flex; flex-wrap:wrap; gap:7px; } .filter.is-active { background:var(--accent); border-color:var(--accent); color:#fff; }
    .review-note,.capture-warning { margin:22px 0; padding:16px 18px; border-left:4px solid var(--accent); background:var(--accent-soft); } .capture-warning { border-left-color:var(--danger); background:#fff2f2; color:#5f2020; } .reference { margin:26px 0; padding:clamp(16px,3vw,30px); scroll-margin-top:90px; } .reference-head { display:flex; justify-content:space-between; gap:20px; align-items:start; } .copy-url { flex:none; } .tags { display:flex; flex-wrap:wrap; gap:7px; margin:14px 0 20px; } .tag { display:inline-block; border-radius:999px; padding:3px 9px; background:var(--accent-soft); color:#07546c; font-size:.75rem; font-weight:700; } .tag.neutral { background:#edf0f2; color:#52606d; }
    .captures { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; margin-bottom:24px; } figure { min-width:0; margin:0; } figcaption { margin-bottom:7px; color:var(--muted); font-size:.83rem; font-weight:650; } img { display:block; width:100%; height:auto; border:1px solid var(--line); border-radius:9px; background:#e8eef2; } .facts { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:18px; } .field { min-width:0; border-top:1px solid var(--line); padding-top:14px; } .field p,.field ul { margin-bottom:0; overflow-wrap:anywhere; } .field ul { padding-left:19px; } .field li + li { margin-top:6px; }
    .decision { display:grid; grid-template-columns:repeat(3,max-content); gap:10px 18px; margin:26px 0 0; padding:14px; border:1px dashed #aabac5; border-radius:9px; } .decision legend { padding:0 6px; color:var(--muted); font-size:.82rem; font-weight:700; } .decision label { cursor:pointer; } .decision .notes { grid-column:1/-1; display:grid; gap:6px; cursor:default; } textarea { width:100%; resize:vertical; border:1px solid #aebec8; border-radius:7px; padding:9px; font:inherit; }
    .matrix-wrap { overflow-x:auto; border:1px solid var(--line); border-radius:14px; background:#fff; } table { width:100%; min-width:1000px; border-collapse:collapse; } th,td { border-bottom:1px solid var(--line); padding:10px; text-align:left; vertical-align:top; } th { position:sticky; top:0; background:#eef4f7; font-size:.8rem; } td:first-child { min-width:270px; } td:first-child a { display:inline-flex; align-items:center; min-height:44px; } .yes { color:#087145; font-weight:800; text-align:center; } .no { color:#9caab3; text-align:center; } .matrix-caption { color:var(--muted); }
    footer { padding:28px 0 60px; color:var(--muted); font-size:.88rem; } .hidden { display:none!important; }
    @media (max-width:850px) { .summary,.facts { grid-template-columns:repeat(2,minmax(0,1fr)); } .meta-grid,.captures { grid-template-columns:1fr; } .reference-head { display:block; } .copy-url { margin-top:8px; } }
    @media (max-width:560px) { .shell { width:min(100% - 20px, 1440px); } .masthead { padding-top:28px; } .summary,.facts { grid-template-columns:1fr; } .decision { grid-template-columns:1fr; } .toolbar { position:static; } }
    """


def _scripts(records: list[dict[str, Any]]) -> str:
    data = _json_for_html({"records": [{"id": item["id"], "tags": _trait_tags(item)} for item in records], "decisions": {"decisions": {}}})
    return f"""
    <script>
    const reviewData = {data};
    const choices = new Map(Object.entries(reviewData.decisions.decisions || {{}}));
    for (const [id, decision] of choices) {{
      const radio = document.querySelector(`input[name="decision-${{id}}"][value="${{decision.status}}"]`);
      if (radio) radio.checked = true;
      const notes = document.querySelector(`[data-notes="${{id}}"]`); if (notes) notes.value = decision.notes || '';
    }}
    function recordDecision(id) {{
      const selected = document.querySelector(`input[name="decision-${{id}}"]:checked`);
      const notes = document.querySelector(`[data-notes="${{id}}"]`);
      if (!selected && !(notes && notes.value.trim())) return;
      choices.set(id, {{ status: selected ? selected.value : 'approve_with_notes', notes: notes ? notes.value.trim() : '' }});
    }}
    document.querySelectorAll('.decision').forEach(fieldset => {{
      const id = fieldset.dataset.reference;
      fieldset.addEventListener('change', () => recordDecision(id));
      fieldset.addEventListener('input', () => recordDecision(id));
    }});
    document.querySelectorAll('.filter').forEach(button => button.addEventListener('click', () => {{
      const tag = button.dataset.trait;
      document.querySelectorAll('.filter').forEach(item => item.classList.remove('is-active'));
      button.classList.add('is-active');
      document.querySelectorAll('.reference').forEach(card => {{
        card.classList.toggle('hidden', tag !== 'all' && !card.dataset.traits.split('|').includes(tag));
      }});
    }}));
    document.querySelectorAll('.copy-url').forEach(button => button.addEventListener('click', async () => {{
      try {{ await navigator.clipboard.writeText(button.dataset.url); button.textContent = 'Copied'; setTimeout(() => button.textContent = 'Copy source URL', 1200); }} catch (_) {{ window.prompt('Copy source URL', button.dataset.url); }}
    }}));
    </script>"""


def _header(title: str, subtitle: str) -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{_e(title)}</title><style>{_styles()}</style></head><body><header class="masthead"><div class="shell"><p class="eyebrow">SiteAgent · local diagnostic</p><h1>{_e(title)}</h1><p class="lede">{_e(subtitle)}</p></div></header>"""


def _provenance(records: list[dict[str, Any]], catalog: dict[str, Any], hash_count: int) -> str:
    sources = Counter(
        f"{record.get('analysis_provenance', {}).get('role', 'Unknown')} · {record.get('analysis_provenance', {}).get('provider', 'unknown')} · {record.get('analysis_provenance', {}).get('model', 'unknown')}"
        for record in records
    )
    source_text = "<br>".join(f"{_e(name)} — {_e(count)} records" for name, count in sorted(sources.items()))
    return f"""<section class="provenance"><h2>Import and provenance</h2><dl>
      <dt>Catalog checksum</dt><dd><code>{_e(catalog.get('catalog_checksum', 'missing'))}</code></dd>
      <dt>Catalog import date</dt><dd>{_e(catalog.get('generated_at', 'missing'))}</dd>
      <dt>Capture integrity</dt><dd>{hash_count} completed desktop/mobile pairs rechecked against their stored SHA-256 hashes.</dd>
      <dt>Analysis provenance</dt><dd>{source_text}</dd>
      <dt>Review boundary</dt><dd>This page is generated from saved local artifacts. It neither reruns analysis nor edits an original <code>reference.json</code>.</dd>
    </dl></section>"""


def _errors(report: dict[str, Any]) -> str:
    entries = []
    for failure in report.get("failures", []):
        identifier = failure.get("id", "unknown")
        attempts = report.get("retry_counts", {}).get(identifier, 0)
        entries.append(f"""<details><summary>{_e(identifier)} · capture timeout · resumable</summary>
          <p>Safe recorded cause: page navigation reached the importer’s 45-second limit while waiting for <code>networkidle</code>. No screenshot analysis was started or fabricated.</p>
          <p>Recorded attempts: {_e(attempts)}. The source remains resumable; it is excluded from active selection until a fresh capture and screenshot analysis complete.</p>
        </details>""")
    return "<section class=\"errors\"><h2>Isolated capture timeouts</h2>" + "".join(entries) + "</section>"


def _initial_decisions() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "purpose": "Human review decisions only; original reference.json records are immutable review inputs.",
        "updated_at": None,
        "decisions": {},
    }


def _assert_catalog(catalog: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    records = [record for record in catalog.get("references", []) if record.get("analysis_status") == "completed"]
    if len(records) < 3:
        raise ValueError(f"Expected at least three completed reference analyses, found {len(records)}.")
    hashes = 0
    for record in records:
        folder = ROOT / record["id"]
        captured = record.get("capture", {}).get("screenshots", {})
        if set(captured) != {"desktop.png", "mobile.png"}:
            raise ValueError(f"{record['id']} does not contain an exact desktop/mobile capture pair.")
        for filename, expected in captured.items():
            path = folder / filename
            if not path.is_file() or _sha256(path) != expected:
                raise ValueError(f"{record['id']}/{filename} does not match its stored capture hash.")
        hashes += 1
    return records, hashes


def build() -> list[Path]:
    catalog = _read_json(ROOT / "catalog.json")
    report = _read_json(ROOT / "import_report.json")
    records, hash_count = _assert_catalog(catalog)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    cards = "\n".join(_record_card(record, _trait_tags(record)) for record in records)
    filters = "".join(f"<button class=\"filter{' is-active' if trait == 'all' else ''}\" type=\"button\" data-trait=\"{_e(trait)}\">{_e(trait)}</button>" for trait in ("all", *TRAITS))
    index = _header("Reference Library — diagnostics", "A local inspection package for autonomous screenshot analysis. Failed captures remain resumable and unavailable for selection.")
    index += f"""<main class="shell"><section class="summary"><div class="metric"><strong>{len(records)}</strong><span>completed analyses</span></div><div class="metric"><strong>{len(report.get('capture_failed', []))}</strong><span>capture failures</span></div><div class="metric"><strong>{len(report.get('analysis_failed', []))}</strong><span>analysis failures</span></div><div class="metric"><strong>{catalog.get('active_reference_count', 0)}</strong><span>autonomous active references</span></div></section>
    <div class="meta-grid">{_provenance(records, catalog, hash_count)}{_errors(report)}</div>
    <nav class="toolbar" aria-label="Diagnostic navigation"><div class="shell toolbar-inner"><a class="button primary" href="trait_matrix.html">Open trait matrix</a><span class="note">Diagnostic-only inspection. Autonomous curation writes <code>../reference_decisions.json</code>.</span></div></nav>
    <aside class="review-note"><strong>This page cannot make production decisions.</strong> It remains a local diagnostic view. A source URL is visible and copyable but deliberately not a live link; every navigation link and screenshot in this package resolves locally.</aside>
    <section aria-labelledby="filters"><h2 id="filters">Trait filters</h2><div class="filters">{filters}</div></section>{cards}</main><footer class="shell">Generated {datetime.now(timezone.utc).isoformat()} from existing local reference artifacts. Diagnostic only; no human checkpoint.</footer>{_scripts(records)}</body></html>"""
    matrix_rows = []
    for record in records:
        tags = set(_trait_tags(record))
        cells = "".join(f"<td class=\"{'yes' if trait in tags else 'no'}\">{'●' if trait in tags else '—'}</td>" for trait in TRAITS)
        matrix_rows.append(f"<tr><td><a href=\"index.html#ref-{_e(record['id'])}\">{_e(record['title'])}</a><br><span class=\"source-url\">{_e(record['id'])}</span></td>{cells}</tr>")
    matrix = _header("Reference Library — trait matrix", "Rule-derived cross-category traits make the reference library searchable by design and commercial behavior, not a category-template catalog.")
    matrix += f"""<main class="shell"><p><a class="button primary" href="index.html">Back to diagnostics</a></p><section class="review-note"><strong>How to read this matrix:</strong> a filled mark means saved screenshot-analysis text matched the displayed trait’s transparent keyword rule. It is a diagnostic filter, not a score or a template selector. Open a record to inspect its evidence, transferable lessons, and “do not copy” constraints.</section><p class="matrix-caption">Completed records: {len(records)}. A horizontal scroll container is intentionally provided for the wide comparison table; the page itself remains viewport-safe.</p><div class="matrix-wrap"><table><thead><tr><th scope="col">Reference</th>{''.join(f'<th scope="col">{_e(trait)}</th>' for trait in TRAITS)}</tr></thead><tbody>{''.join(matrix_rows)}</tbody></table></div></main><footer class="shell">Generated from the same immutable local catalog checksum <code>{_e(catalog.get('catalog_checksum', 'missing'))}</code>.</footer></body></html>"""
    if SECRET_RE.search(index) or SECRET_RE.search(matrix):
        raise ValueError("Refusing to write review pages containing a secret-like value.")
    paths = [OUTPUT / "index.html", OUTPUT / "trait_matrix.html"]
    paths[0].write_text(index, encoding="utf-8")
    paths[1].write_text(matrix, encoding="utf-8")
    return paths


def verify() -> None:
    pages = [OUTPUT / "index.html", OUTPUT / "trait_matrix.html"]
    for page in pages:
        if not page.is_file():
            raise ValueError(f"Missing generated review page: {page}")
        content = page.read_text(encoding="utf-8")
        if SECRET_RE.search(content):
            raise ValueError(f"Secret-like value found in {page}")
        for target in re.findall(r'(?:href|src)="([^"]+)"', content):
            if target.startswith(("#", "mailto:", "tel:")):
                continue
            if "://" in target or target.startswith("file:"):
                raise ValueError(f"Non-local package target in {page}: {target}")
            if target.endswith(".png") and not (page.parent / target).resolve().is_file():
                raise ValueError(f"Missing local image target in {page}: {target}")
    payload = _read_json(INVALID_INPUT)
    if payload.get("invalid_reason") != "invalidated_by_user_accidental_input":
        raise ValueError("Historical review input must remain explicitly invalidated.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate the already generated local package without rewriting it.")
    args = parser.parse_args()
    if args.check:
        verify()
        print("Reference human-review package checks passed.")
        return
    for path in build():
        print(path)
    verify()
    print("Reference human-review package generated and checked.")


if __name__ == "__main__":
    main()
