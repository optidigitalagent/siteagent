"""Bounded public-source collection for the one-link preview intake contract.

This module deliberately exposes provider seams instead of embedding a browser or
search-engine dependency in the production process.  An orchestrator may inject
web-search, browser, or official-site providers; every attempt is bounded and
recorded in the source ledger.
"""
from __future__ import annotations

import re
import ipaddress
import socket
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from site_agent.identifiers import normalize_instagram_url
from site_agent.instagram import InstagramScraper, ScrapedInstagram


@dataclass(frozen=True)
class PublicSource:
    url: str
    source_kind: str
    title: str = ""
    description: str = ""
    text: str = ""
    image_urls: tuple[str, ...] = ()
    video_urls: tuple[str, ...] = ()
    outbound_urls: tuple[str, ...] = ()
    status_code: int | None = None


@dataclass(frozen=True)
class SourceLedgerEntry:
    provider: str
    source_kind: str
    url: str
    status: str
    status_code: int | None = None
    facts_found: int = 0
    images_found: int = 0
    videos_found: int = 0
    error: str = ""


@dataclass
class OneLinkResearch:
    submitted_url: str
    normalized_url: str
    source_kind: str
    business_name: str
    working_name_inferred: bool
    business_identified: bool
    title: str = ""
    description: str = ""
    public_text: str = ""
    image_urls: list[str] = field(default_factory=list)
    video_urls: list[str] = field(default_factory=list)
    official_site_urls: list[str] = field(default_factory=list)
    sources: list[PublicSource] = field(default_factory=list)
    source_ledger: list[SourceLedgerEntry] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def has_full_preview_media(self) -> bool:
        # Video candidates are provenance-only until they have been downloaded,
        # validated, and uploaded for Studio delivery.  They must not stop the
        # bounded fallbacks before six renderable image candidates are found.
        return len(self.image_urls) >= 6

    def media_candidates(self) -> list[dict]:
        candidates = [
            {
                "url": url,
                "kind": "image",
                "source_url": self.normalized_url,
                "source_kind": "business_social" if self.source_kind == "instagram" else "business_web",
            }
            for url in self.image_urls
        ]
        candidates.extend(
            {
                "url": url,
                "kind": "video",
                "source_url": self.normalized_url,
                "source_kind": "business_social" if self.source_kind == "instagram" else "business_web",
                "metadata_only": True,
            }
            for url in self.video_urls
        )
        return candidates

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["has_full_preview_media"] = self.has_full_preview_media
        payload["media_candidates"] = self.media_candidates()
        return payload

    def write_source_ledger(self, path: Path) -> None:
        import json

        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps({"schema_version": 1, "sources": [asdict(item) for item in self.source_ledger]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)


FallbackProvider = Callable[[str], PublicSource | dict | Iterable[PublicSource | dict] | None]


def normalize_business_source(value: str) -> tuple[str, str]:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("A business or Instagram URL is required.")
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlsplit(raw)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    if not host:
        raise ValueError("The submitted source is not a valid public URL.")
    if host == "instagram.com" or host.endswith(".instagram.com"):
        return normalize_instagram_url(raw), "instagram"
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    normalized = urlunsplit(("https", host, path.rstrip("/") or "/", "", ""))
    return normalized, "business_web"


class OneLinkResearcher:
    """Collect static evidence, then invoke each configured fallback at most once."""

    def __init__(
        self,
        *,
        scraper: InstagramScraper | None = None,
        web_fallback: FallbackProvider | None = None,
        browser_fallback: FallbackProvider | None = None,
        official_site_fallback: FallbackProvider | None = None,
        max_sources: int = 8,
        max_images: int = 24,
        max_videos: int = 8,
    ) -> None:
        self.scraper = scraper or InstagramScraper(max_media=max_images)
        self.fallbacks = (
            ("web", web_fallback),
            ("browser", browser_fallback),
            ("official_site", official_site_fallback),
        )
        self.max_sources = max(1, max_sources)
        self.max_images = max(1, max_images)
        self.max_videos = max(1, max_videos)

    def collect(self, source_url: str) -> OneLinkResearch:
        normalized, source_kind = normalize_business_source(source_url)
        scraped = self.scraper.fetch(normalized)
        primary = self._from_scrape(scraped, source_kind)
        sources = [primary]
        ledger = [self._ledger("static", primary, scraped.errors)]
        errors = list(scraped.errors)

        for provider_name, provider in self.fallbacks:
            if provider is None or len(sources) >= self.max_sources:
                continue
            # Enough profile media may end browser fallback, but it must never
            # suppress a discovered official-site fact source.
            if provider_name != "official_site" and self._enough(sources):
                continue
            target_url = normalized
            if provider_name == "official_site":
                discovered = self._official_sites(sources, normalized)
                if discovered:
                    target_url = discovered[0]
            try:
                returned = provider(target_url)
                additions = self._coerce_many(returned, provider_name)
                if not additions:
                    ledger.append(SourceLedgerEntry(provider_name, provider_name, target_url, "empty"))
                    continue
                for source in additions[: self.max_sources - len(sources)]:
                    sources.append(source)
                    ledger.append(self._ledger(provider_name, source, []))
            except Exception as exc:  # provider failures are evidence, not process crashes
                message = f"{provider_name} fallback failed: {exc}"
                errors.append(message)
                ledger.append(SourceLedgerEntry(provider_name, provider_name, target_url, "failed", error=str(exc)))

        media_sources = self._business_media_sources(sources)
        images = self._unique_url((source.image_urls for source in media_sources), self.max_images)
        videos = self._unique_url((source.video_urls for source in media_sources), self.max_videos)
        text = " ".join(part for source in sources for part in (source.title, source.description, source.text) if part)
        title = next((source.title for source in sources if source.title), "")
        description = next((source.description for source in sources if source.description), "")
        name, inferred = self._business_name(title, normalized)
        official = self._official_sites(sources, normalized)
        identified = bool(name and (title or description or self._meaningful_handle(normalized)))
        return OneLinkResearch(
            submitted_url=source_url,
            normalized_url=normalized,
            source_kind=source_kind,
            business_name=name,
            working_name_inferred=inferred,
            business_identified=identified,
            title=title,
            description=description,
            public_text=re.sub(r"\s+", " ", text).strip()[:16000],
            image_urls=images,
            video_urls=videos,
            official_site_urls=official,
            sources=sources,
            source_ledger=ledger,
            errors=errors,
        )

    def _from_scrape(self, value: ScrapedInstagram, kind: str) -> PublicSource:
        return PublicSource(
            url=value.canonical or value.url,
            source_kind=kind,
            title=value.title,
            description=value.description,
            text=value.page_text,
            image_urls=tuple(value.image_urls),
            video_urls=tuple(value.video_urls),
            outbound_urls=tuple(value.outbound_urls),
            status_code=value.status_code,
        )

    @staticmethod
    def _coerce_many(value, provider_name: str) -> list[PublicSource]:
        if value is None:
            return []
        if isinstance(value, (PublicSource, dict)):
            values = [value]
        else:
            values = list(value)
        result = []
        for item in values:
            if isinstance(item, PublicSource):
                result.append(item)
            elif isinstance(item, dict) and item.get("url"):
                result.append(PublicSource(
                    url=str(item["url"]), source_kind=str(item.get("source_kind", provider_name)),
                    title=str(item.get("title", "")), description=str(item.get("description", "")),
                    text=str(item.get("text", item.get("page_text", ""))),
                    image_urls=tuple(item.get("image_urls", ())), video_urls=tuple(item.get("video_urls", ())),
                    outbound_urls=tuple(item.get("outbound_urls", ())), status_code=item.get("status_code"),
                ))
        return result

    def _enough(self, sources: list[PublicSource]) -> bool:
        media_sources = self._business_media_sources(sources)
        images = self._unique_url((source.image_urls for source in media_sources), self.max_images)
        identity = any(source.title or source.description or source.text for source in sources)
        return identity and len(images) >= 6

    @staticmethod
    def _business_media_sources(sources: list[PublicSource]) -> list[PublicSource]:
        trusted = {"instagram", "business_social", "browser", "official_site", "business_web"}
        return [source for source in sources if source.source_kind in trusted]

    @staticmethod
    def _unique_url(groups, limit: int) -> list[str]:
        values = []
        for group in groups:
            for value in group:
                url = str(value or "").strip()
                if InstagramScraper.is_public_http_url(url) and url not in values:
                    values.append(url)
                    if len(values) >= limit:
                        return values
        return values

    @staticmethod
    def _ledger(provider: str, source: PublicSource, errors: list[str]) -> SourceLedgerEntry:
        facts = sum(bool(value) for value in (source.title, source.description, source.text))
        return SourceLedgerEntry(
            provider=provider, source_kind=source.source_kind, url=source.url,
            status="failed" if errors and not facts else "collected", status_code=source.status_code,
            facts_found=facts, images_found=len(source.image_urls), videos_found=len(source.video_urls),
            error="; ".join(errors),
        )

    @staticmethod
    def _business_name(title: str, normalized_url: str) -> tuple[str, bool]:
        cleaned = re.sub(r"\s*[|\-]\s*Instagram.*$", "", title or "", flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"^Instagram\s*", "", cleaned, flags=re.IGNORECASE).strip()
        if cleaned:
            return cleaned[:160], False
        handle = urlsplit(normalized_url).path.strip("/").split("/")[0]
        working = re.sub(r"[._-]+", " ", handle).strip().title()
        return (working or urlsplit(normalized_url).hostname or "Business")[:160], True

    @staticmethod
    def _meaningful_handle(normalized_url: str) -> bool:
        handle = urlsplit(normalized_url).path.strip("/").split("/")[0]
        return bool(handle and handle not in {"p", "reel", "stories", "explore"})

    @staticmethod
    def _official_sites(sources: list[PublicSource], normalized_url: str) -> list[str]:
        primary_host = (urlsplit(normalized_url).hostname or "").removeprefix("www.")
        excluded = {primary_host, "facebook.com", "youtube.com", "tiktok.com", "x.com", "twitter.com"}
        values = []
        for source in sources:
            candidates = list(source.outbound_urls)
            if source.source_kind in {"official_site", "business_web"}:
                candidates.insert(0, source.url)
            for value in candidates:
                if not InstagramScraper.is_public_http_url(value):
                    continue
                host = (urlsplit(value).hostname or "").removeprefix("www.")
                if host and not any(host == item or host.endswith("." + item) for item in excluded) and value not in values:
                    values.append(value)
        return values[:8]


def bootstrap_one_link_intake(
    source_url: str,
    run_dir: Path,
    *,
    researcher: OneLinkResearcher | None = None,
    media_ingestor=None,
) -> dict:
    """Orchestrator integration seam: research, ledger, and preview manifest."""
    from site_agent.media import PreviewMediaIngestor
    from site_agent.media import MediaInputBlocked

    result = (researcher or default_one_link_researcher()).collect(source_url)
    result.write_source_ledger(run_dir / "generation_reports" / "source_ledger.json")
    if not result.business_identified:
        raise MediaInputBlocked("one-link intake blocked: the submitted URL could not be identified as a business")
    manifest = (media_ingestor or PreviewMediaIngestor()).ingest(
        result.media_candidates(), run_dir / "media_input", submitted_source_url=result.normalized_url
    )
    return {"research": result.to_dict(), "media_manifest": manifest}


def default_one_link_researcher() -> OneLinkResearcher:
    """Runtime collector with bounded static, web, browser and official-site fallbacks."""
    return OneLinkResearcher(
        web_fallback=web_search_fallback,
        browser_fallback=browser_fallback,
        official_site_fallback=official_site_fallback,
    )


def web_search_fallback(source_url: str) -> list[PublicSource]:
    """Discover public corroboration when the submitted page is incomplete."""
    normalized, _ = normalize_business_source(source_url)
    handle = urlsplit(normalized).path.strip("/").split("/")[0].replace("_", " ")
    response = requests.get(
        "https://www.google.com/search",
        params={"q": f'"{handle}" business official site'},
        headers={"User-Agent": "Mozilla/5.0 SiteAgent public research", "Accept-Language": "uk,en;q=0.8"},
        timeout=20,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    links: list[str] = []
    for anchor in soup.select("a[href]"):
        href = str(anchor.get("href", ""))
        if href.startswith("/url?q="):
            href = href.split("/url?q=", 1)[1].split("&", 1)[0]
        if not InstagramScraper.is_public_http_url(href):
            continue
        host = (urlsplit(href).hostname or "").lower()
        if any(token in host for token in ("google.", "gstatic.", "instagram.com")):
            continue
        if href not in links:
            links.append(href)
        if len(links) >= 5:
            break
    text = " ".join(node.get_text(" ", strip=True) for node in soup.select("h3, [data-sncf], .VwiC3b"))
    return [PublicSource(
        url=response.url or "https://www.google.com/search",
        source_kind="web_search",
        title=f"Public search results for {handle}",
        text=re.sub(r"\s+", " ", text)[:6000],
        outbound_urls=tuple(links),
        status_code=response.status_code,
    )]


def browser_fallback(source_url: str) -> PublicSource:
    """Render the submitted business page when its static response is a login shell."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, channel="chrome")
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 2200}, locale="uk-UA")
            response = page.goto(source_url, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(3500)
            payload = page.evaluate("""() => ({
                title: document.title,
                text: document.body?.innerText || '',
                images: [...document.images].filter(i => i.naturalWidth >= 320 && i.naturalHeight >= 320).map(i => i.currentSrc || i.src),
                videos: [...document.querySelectorAll('video')].map(v => v.currentSrc || v.src).filter(Boolean),
                links: [...document.querySelectorAll('a[href]')].map(a => a.href)
            })""")
            return PublicSource(
                url=source_url,
                source_kind="browser",
                title=str(payload.get("title", "")),
                text=str(payload.get("text", ""))[:12000],
                image_urls=tuple(payload.get("images", ())),
                video_urls=tuple(payload.get("videos", ())),
                outbound_urls=tuple(payload.get("links", ())),
                status_code=response.status if response else None,
            )
        finally:
            browser.close()


def official_site_fallback(source_url: str) -> PublicSource:
    """Read a discovered official site without admitting private-network targets."""
    _assert_public_network_url(source_url)
    response = requests.get(
        source_url,
        headers={"User-Agent": "Mozilla/5.0 SiteAgent official-site research", "Accept-Language": "uk,en;q=0.8"},
        timeout=25,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    images = []
    for image in soup.select("img[src], img[srcset]"):
        value = str(image.get("src", ""))
        if not value and image.get("srcset"):
            value = str(image.get("srcset")).split(",", 1)[0].strip().split(" ", 1)[0]
        if value:
            from urllib.parse import urljoin
            value = urljoin(response.url, value)
            if InstagramScraper.is_public_http_url(value):
                images.append(value)
    outbound = [str(anchor.get("href")) for anchor in soup.select("a[href]")]
    return PublicSource(
        url=response.url,
        source_kind="official_site",
        title=(soup.title.get_text(" ", strip=True) if soup.title else ""),
        description=str((soup.find("meta", attrs={"name": "description"}) or {}).get("content", "")),
        text=re.sub(r"\s+", " ", soup.get_text(" ", strip=True))[:16000],
        image_urls=tuple(dict.fromkeys(images[:24])),
        outbound_urls=tuple(outbound[:30]),
        status_code=response.status_code,
    )


def _assert_public_network_url(value: str) -> None:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Official-site fallback requires an HTTP(S) public URL.")
    for address in socket.getaddrinfo(parsed.hostname, None):
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ValueError("Official-site fallback refused a non-public network target.")
