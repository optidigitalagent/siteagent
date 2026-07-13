from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

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
            "visible_text:",
            self.page_text[:4000],
            "fetch_errors:",
            *[f"- {error}" for error in self.errors],
        ]
        return "\n".join(lines)


class InstagramScraper:
    def fetch(self, instagram_url: str) -> ScrapedInstagram:
        scraped = ScrapedInstagram(url=instagram_url)
        try:
            response = requests.get(
                instagram_url,
                headers={"User-Agent": USER_AGENT, "Accept-Language": "en,ru;q=0.9,ar;q=0.8"},
                timeout=20,
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
        attr = "src"
        tags = soup.find_all("img" if kind == "image" else "video")
        for tag in tags:
            value = tag.get(attr) or tag.get("poster")
            if value:
                urls.append(urljoin(base_url, str(value)))
        return list(dict.fromkeys(urls))

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text)
        noisy = ["Instagram", "Log in", "Sign up", "Meta", "Threads"]
        for token in noisy:
            text = text.replace(token, " ")
        return re.sub(r"\s+", " ", text).strip()

