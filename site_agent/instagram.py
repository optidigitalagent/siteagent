from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


@dataclass
class ScrapedInstagram:
    url: str
    status_code: int | None = None
    title: str = ""
    description: str = ""
    canonical: str = ""
    image_urls: list[str] = field(default_factory=list)
    video_urls: list[str] = field(default_factory=list)
    outbound_urls: list[str] = field(default_factory=list)
    page_text: str = ""
    errors: list[str] = field(default_factory=list)

    def to_context(self) -> str:
        lines = [
            f"url: {self.url}",
            f"status_code: {self.status_code}",
            f"title: {self.title}",
            f"description: {self.description}",
            f"canonical: {self.canonical}",
            "image_urls:",
            *[f"- {url}" for url in self.image_urls[:20]],
            "video_urls:",
            *[f"- {url}" for url in self.video_urls[:10]],
            "outbound_urls:",
            *[f"- {url}" for url in self.outbound_urls[:20]],
            "visible_text:",
            self.page_text[:4000],
            "fetch_errors:",
            *[f"- {error}" for error in self.errors],
        ]
        return "\n".join(lines)


class InstagramScraper:
    def __init__(self, *, get=None, timeout: int = 20, max_media: int = 30) -> None:
        self.get = get or requests.get
        self.timeout = timeout
        self.max_media = max(1, max_media)

    def fetch(self, instagram_url: str) -> ScrapedInstagram:
        scraped = ScrapedInstagram(url=instagram_url)
        try:
            response = self.get(
                instagram_url,
                headers={"User-Agent": USER_AGENT, "Accept-Language": "en,ru;q=0.9,ar;q=0.8"},
                timeout=self.timeout,
            )
            scraped.status_code = response.status_code
            response.raise_for_status()
        except requests.RequestException as exc:
            scraped.errors.append(f"Public Instagram fetch failed: {exc}")
            return scraped

        soup = BeautifulSoup(response.text, "html.parser")
        scraped.title = self._meta(soup, "og:title") or self._title(soup)
        scraped.description = self._meta(soup, "og:description") or self._meta(soup, "description")
        scraped.canonical = self._canonical(soup) or instagram_url
        scraped.image_urls = self._media_urls(soup, "image", instagram_url)
        scraped.video_urls = self._media_urls(soup, "video", instagram_url)
        scraped.outbound_urls = self._outbound_urls(soup, instagram_url)
        scraped.page_text = self._clean_text(soup.get_text(" ", strip=True))
        return scraped

    def _title(self, soup: BeautifulSoup) -> str:
        if soup.title and soup.title.string:
            return soup.title.string.strip()
        return ""

    def _meta(self, soup: BeautifulSoup, name: str) -> str:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        return str(tag.get("content", "")).strip() if tag else ""

    def _canonical(self, soup: BeautifulSoup) -> str:
        tag = soup.find("link", attrs={"rel": "canonical"})
        return str(tag.get("href", "")).strip() if tag else ""

    def _media_urls(self, soup: BeautifulSoup, kind: str, base_url: str) -> list[str]:
        urls: list[str] = []
        meta_keys = [f"og:{kind}", f"twitter:{kind}"]
        for key in meta_keys:
            value = self._meta(soup, key)
            if value:
                urls.append(urljoin(base_url, value))
        tags = soup.find_all("img" if kind == "image" else "video")
        for tag in tags:
            # A poster is an image candidate, not evidence that a playable
            # video URL exists.  Counting posters as videos would incorrectly
            # satisfy the four-images-plus-video threshold.
            values = [tag.get("src")]
            values.extend(source.get("src") for source in tag.find_all("source"))
            srcset = str(tag.get("srcset", ""))
            values.extend(part.strip().split(" ", 1)[0] for part in srcset.split(",") if part.strip())
            for value in values:
                if value:
                    urls.append(urljoin(base_url, str(value)))
        if kind == "image":
            for tag in soup.find_all("video", poster=True):
                urls.append(urljoin(base_url, str(tag.get("poster", ""))))
        filtered = [url for url in urls if self.is_public_http_url(url)]
        return list(dict.fromkeys(filtered))[: self.max_media]

    def _outbound_urls(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        urls = []
        for tag in soup.find_all("a", href=True):
            url = urljoin(base_url, str(tag.get("href", "")))
            if self.is_public_http_url(url):
                urls.append(url)
        return list(dict.fromkeys(urls))[:40]

    @staticmethod
    def is_public_http_url(value: str) -> bool:
        """Reject browser-only and embedded payload URLs before they reach intake."""
        raw = str(value or "").strip()
        if not raw or raw.lower().startswith(("data:", "blob:", "javascript:")):
            return False
        parsed = urlparse(raw)
        return parsed.scheme.lower() in {"http", "https"} and bool(parsed.hostname)

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text)
        noisy = ["Instagram", "Log in", "Sign up", "Meta", "Threads"]
        for token in noisy:
            text = text.replace(token, " ")
        return re.sub(r"\s+", " ", text).strip()
