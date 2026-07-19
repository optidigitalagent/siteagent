from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from site_agent.instagram import InstagramScraper
from site_agent.media import MediaInputBlocked, MediaPreparer, PreviewMediaIngestor
from site_agent.research import OneLinkResearcher, PublicSource, bootstrap_one_link_intake, normalize_business_source


class _Response:
    def __init__(self, content: bytes, *, status: int = 200, content_type: str = "text/html", url: str = "") -> None:
        self.content = content
        self.text = content.decode("utf-8", errors="ignore")
        self.status_code = status
        self.headers = {"Content-Type": content_type}
        self.url = url

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _image_bytes(color: tuple[int, int, int]) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (900, 700), color).save(buffer, "JPEG", quality=90)
    return buffer.getvalue()


class OneLinkResearchTests(unittest.TestCase):
    def test_normalizes_instagram_and_business_sources(self) -> None:
        self.assertEqual(
            normalize_business_source("www.instagram.com/Example/?utm_source=x"),
            ("https://instagram.com/example", "instagram"),
        )
        self.assertEqual(
            normalize_business_source("http://WWW.EXAMPLE.COM/services/?x=1"),
            ("https://example.com/services", "business_web"),
        )

    def test_static_scrape_filters_embedded_urls_and_collects_links(self) -> None:
        html = b"""<html><head>
        <meta property='og:title' content='Atelier One | Instagram'>
        <meta property='og:image' content='https://cdn.example/hero.jpg'>
        </head><body>
        <img src='data:image/png;base64,AAAA'><img src='blob:https://instagram.com/id'>
        <img src='https://cdn.example/work.jpg'>
        <video poster='https://cdn.example/reel-cover.jpg'></video>
        <a href='https://atelier.example/'>Official</a>
        </body></html>"""
        scraper = InstagramScraper(get=lambda *args, **kwargs: _Response(html))
        result = scraper.fetch("https://instagram.com/atelier_one")
        self.assertEqual(result.image_urls, ["https://cdn.example/hero.jpg", "https://cdn.example/work.jpg", "https://cdn.example/reel-cover.jpg"])
        self.assertEqual(result.video_urls, [])
        self.assertEqual(result.outbound_urls, ["https://atelier.example/"])

    def test_access_failure_invokes_bounded_fallbacks_and_records_ledger(self) -> None:
        calls = []

        def failed(*args, **kwargs):
            raise __import__("requests").RequestException("login wall")

        def web(url):
            calls.append("web")
            return PublicSource(url="https://directory.example/atelier", source_kind="web_search", title="Atelier One")

        def browser(url):
            calls.append("browser")
            return {"url": url, "source_kind": "browser", "image_urls": [f"https://cdn.example/{i}.jpg" for i in range(6)]}

        def official(url):
            calls.append("official")
            return {"url": "https://atelier.example", "source_kind": "official_site", "text": "Official services"}

        result = OneLinkResearcher(
            scraper=InstagramScraper(get=failed), web_fallback=web,
            browser_fallback=browser, official_site_fallback=official, max_sources=5,
        ).collect("https://instagram.com/atelier_one")
        self.assertEqual(calls, ["web", "browser", "official"])
        self.assertEqual(len(result.image_urls), 6)
        self.assertTrue(result.business_identified)
        self.assertEqual([item.provider for item in result.source_ledger], ["static", "web", "browser", "official_site"])
        self.assertEqual(result.source_ledger[0].status, "failed")

    def test_official_site_fallback_receives_discovered_business_link(self) -> None:
        html = b"<html><head><title>Atelier</title></head><body><a href='https://atelier.example/'>Site</a></body></html>"
        received = []

        def official(url):
            received.append(url)
            return {
                "url": url, "source_kind": "official_site", "text": "Official business services",
                "image_urls": [f"https://atelier.example/media/{index}.jpg" for index in range(6)],
            }

        result = OneLinkResearcher(
            scraper=InstagramScraper(get=lambda *args, **kwargs: _Response(html)),
            web_fallback=lambda url: None, browser_fallback=lambda url: None,
            official_site_fallback=official,
        ).collect("https://instagram.com/atelier")
        self.assertEqual(received, ["https://atelier.example/"])
        self.assertEqual(len(result.image_urls), 6)
        self.assertEqual(result.source_ledger[-1].source_kind, "official_site")

    def test_metadata_only_video_does_not_stop_renderable_media_fallback(self) -> None:
        html = """<html><head><title>Atelier</title>
        <meta property='og:video' content='https://cdn.example/reel.mp4'>
        </head><body>
        <img src='https://cdn.example/0.jpg'><img src='https://cdn.example/1.jpg'>
        <img src='https://cdn.example/2.jpg'><img src='https://cdn.example/3.jpg'>
        </body></html>""".encode()
        calls = []

        def web(url):
            calls.append("web")
            return None

        def browser(url):
            calls.append("browser")
            return {
                "url": url,
                "source_kind": "browser",
                "image_urls": ["https://cdn.example/4.jpg", "https://cdn.example/5.jpg"],
            }

        result = OneLinkResearcher(
            scraper=InstagramScraper(get=lambda *args, **kwargs: _Response(html)),
            web_fallback=web,
            browser_fallback=browser,
        ).collect("https://instagram.com/atelier")

        self.assertEqual(calls, ["web", "browser"])
        self.assertEqual(len(result.image_urls), 6)
        self.assertEqual(result.video_urls, ["https://cdn.example/reel.mp4"])
        self.assertTrue(result.has_full_preview_media)

    def test_meta_platform_footer_is_not_an_official_business_site_or_media_source(self) -> None:
        html = b"""<html><head><title>Atelier | Instagram</title></head><body>
        <a href='https://about.meta.com/'>Meta</a>
        <a href='https://www.meta.com/quest/'>Quest</a>
        <img src='https://cdninstagram.com/t51.82787-19/avatar.jpg'>
        </body></html>"""

        result = OneLinkResearcher(
            scraper=InstagramScraper(get=lambda *args, **kwargs: _Response(html)),
            web_fallback=lambda url: PublicSource(
                url="https://search.example", source_kind="web_search",
                outbound_urls=("https://about.meta.com/",),
            ),
            browser_fallback=lambda url: PublicSource(
                url=url,
                source_kind="browser",
                image_urls=(
                    "https://cdninstagram.com/t51.82787-15/post.jpg",
                    "https://cdninstagram.com/t51.82787-15/other-account-post.jpg",
                    "https://lookaside.fbsbx.com/elementpath/media/?media_id=1",
                    "https://scontent.example/t39.8562-6/rayban.jpg",
                ),
                outbound_urls=("https://www.meta.com/ai-glasses/",),
                media_ownership=((
                    "https://cdninstagram.com/t51.82787-15/post.jpg",
                    "submitted_profile_alt_attribution",
                ),),
            ),
        ).collect("https://instagram.com/atelier")

        self.assertEqual(result.official_site_urls, [])
        candidates = result.media_candidates()
        self.assertEqual([item["url"] for item in candidates], [
            "https://cdninstagram.com/t51.82787-19/avatar.jpg",
            "https://cdninstagram.com/t51.82787-15/post.jpg",
        ])
        self.assertTrue(all(item["source_record_id"] for item in candidates))
        self.assertEqual(candidates[0]["source_role"], "profile_avatar")


class PreviewMediaIntakeTests(unittest.TestCase):
    def test_auto_writes_manifest_preserves_originals_and_never_authorizes_production(self) -> None:
        payloads = {f"https://cdninstagram.com/t51.82787-15/{index}.jpg": _image_bytes((index * 20, 50, 100)) for index in range(6)}

        def get(url, **kwargs):
            return _Response(payloads[url], content_type="image/jpeg")

        candidates = [
            {"url": url, "kind": "image", "source_kind": "business_social", "source_url": "https://instagram.com/atelier"}
            for url in payloads
        ]
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "media_input"
            manifest = PreviewMediaIngestor(get=get).ingest(
                candidates, output, submitted_source_url="https://instagram.com/atelier"
            )
            saved = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(saved, manifest)
            self.assertEqual(manifest["image_count"], 6)
            self.assertTrue(manifest["full_preview_media_sufficient"])
            self.assertTrue(all((output / item["original_file"]).is_file() for item in manifest["media"]))
            self.assertTrue(all((output / item["processed_file"]).is_file() for item in manifest["media"]))
            for item in manifest["media"]:
                self.assertEqual(item["source_kind"], "business_social")
                self.assertTrue(item["user_authorized_for_preview"])
                self.assertFalse(item["allowed_for_customer_production"])
                self.assertFalse(item["user_authorized"])
                self.assertFalse(item["allowed_for_public_site"])

            loaded = MediaPreparer.load_candidates(output / "manifest.json")
            with self.assertRaisesRegex(MediaInputBlocked, "source_kind=business"):
                MediaPreparer().prepare(loaded, Path(temp) / "production")

    def test_metadata_only_video_is_provenance_not_studio_ready_media(self) -> None:
        urls = [f"https://cdninstagram.com/t51.82787-15/{index}.jpg" for index in range(4)]

        def get(url, **kwargs):
            index = int(url.rsplit("/", 1)[-1].split(".", 1)[0])
            return _Response(_image_bytes((30 + index * 20, 40, 50)), content_type="image/jpeg")

        candidates = [{"url": url, "kind": "image", "source_kind": "business_social"} for url in urls]
        candidates.append({
            "url": "https://cdninstagram.com/o1/v/t16/reel.mp4", "kind": "video", "metadata_only": True,
            "source_kind": "business_social", "width": 1080, "height": 1920,
        })
        with tempfile.TemporaryDirectory() as temp:
            manifest = PreviewMediaIngestor(get=get).ingest(
                candidates, Path(temp) / "media_input", submitted_source_url="https://instagram.com/atelier"
            )
        self.assertEqual(manifest["image_count"], 4)
        self.assertEqual(manifest["video_count"], 0)
        self.assertEqual(manifest["media_count"], 4)
        self.assertEqual(manifest["metadata_only_media_count"], 1)
        self.assertFalse(manifest["full_preview_media_sufficient"])
        self.assertEqual(manifest["composition_mode"], "adapted_media")
        metadata = manifest["metadata_only_media"][0]
        self.assertEqual(metadata["asset_url"], "https://cdninstagram.com/o1/v/t16/reel.mp4")
        self.assertEqual(metadata["source_kind"], "business_social")
        self.assertTrue(metadata["user_authorized_for_preview"])
        self.assertFalse(metadata["allowed_for_customer_production"])
        self.assertEqual(metadata["download_status"], "metadata_only")
        self.assertNotIn("url", metadata)

    def test_zero_real_media_writes_blocked_manifest_then_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "media_input"
            with self.assertRaisesRegex(MediaInputBlocked, "no provable business media"):
                PreviewMediaIngestor().ingest(
                    [{"url": "data:image/png;base64,AAAA", "kind": "image", "source_kind": "business_social"}],
                    output,
                    submitted_source_url="https://instagram.com/empty",
                )
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["media_count"], 0)
            self.assertEqual(manifest["composition_mode"], "blocked")

    def test_preview_ingestor_rejects_platform_owned_media(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "media_input"
            with self.assertRaisesRegex(MediaInputBlocked, "no provable business media"):
                PreviewMediaIngestor(get=lambda *args, **kwargs: _Response(_image_bytes((0, 0, 255)), content_type="image/jpeg")).ingest(
                    [{
                        "url": "https://lookaside.fbsbx.com/elementpath/media/?media_id=1",
                        "kind": "image",
                        "source_kind": "business_social",
                        "source_role": "platform_chrome",
                    }],
                    output,
                    submitted_source_url="https://instagram.com/atelier",
                )
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["media_count"], 0)
            self.assertEqual(manifest["rejected"][0]["reason"], "platform_owned_media_is_not_business_evidence")

    def test_bootstrap_writes_source_ledger_and_media_manifest(self) -> None:
        urls = tuple(f"https://cdninstagram.com/t51.82787-15/{index}.jpg" for index in range(6))
        source = PublicSource(
            url="https://instagram.com/atelier", source_kind="browser", title="Atelier",
            image_urls=urls,
            media_ownership=tuple((url, "submitted_profile_alt_attribution") for url in urls),
        )
        researcher = OneLinkResearcher(
            scraper=InstagramScraper(get=lambda *args, **kwargs: _Response(b"<html></html>")),
            browser_fallback=lambda url: source,
        )

        def get(url, **kwargs):
            index = int(url.rsplit("/", 1)[-1].split(".", 1)[0])
            return _Response(_image_bytes((index * 15, 80, 90)), content_type="image/jpeg")

        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / "run"
            result = bootstrap_one_link_intake(
                "https://instagram.com/atelier", run, researcher=researcher,
                media_ingestor=PreviewMediaIngestor(get=get),
            )
            self.assertTrue((run / "generation_reports" / "source_ledger.json").is_file())
            self.assertTrue((run / "media_input" / "manifest.json").is_file())
            self.assertEqual(result["media_manifest"]["media_count"], 6)


if __name__ == "__main__":
    unittest.main()
