from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from site_agent.brand import BrandFidelityAuditor, BrandIdentityAnalyzer
from site_agent.orchestrator import SiteAgentOrchestrator


SOURCE = "https://instagram.com/example_dental"


class BrandIdentityTests(unittest.TestCase):
    def _logo(self, root: Path, *, chromatic: bool = True) -> Path:
        originals = root / "media_input" / "originals"
        originals.mkdir(parents=True, exist_ok=True)
        path = originals / "logo.png"
        image = Image.new("RGB", (320, 320), "white")
        draw = ImageDraw.Draw(image)
        if chromatic:
            draw.ellipse((70, 55, 190, 190), fill=(47, 166, 132))
            draw.polygon(((130, 90), (250, 90), (190, 235)), fill=(237, 76, 126))
        else:
            draw.ellipse((70, 55, 220, 220), fill=(25, 25, 25))
        image.save(path)
        return path

    def _graphic(self, root: Path, name: str, colours: tuple[tuple[int, int, int], ...]) -> Path:
        originals = root / "media_input" / "originals"
        originals.mkdir(parents=True, exist_ok=True)
        path = originals / name
        image = Image.new("RGB", (640, 800), colours[0])
        draw = ImageDraw.Draw(image)
        width = image.width // len(colours)
        for index, colour in enumerate(colours):
            draw.rectangle((index * width, 0, (index + 1) * width, image.height), fill=colour)
        image.save(path)
        return path

    @staticmethod
    def _item(path: Path, asset_id: str, *, avatar: bool = False, platform: bool = False) -> dict:
        return {
            "asset_id": asset_id,
            "kind": "image",
            "asset_url": (
                "https://lookaside.fbsbx.com/elementpath/media/?media_id=1"
                if platform
                else "https://cdninstagram.com/t51.82787-19/avatar.jpg"
                if avatar
                else f"https://cdninstagram.com/t51.82787-15/{asset_id}.jpg"
            ),
            "source_kind": "business_social",
            "source_url": SOURCE,
            "user_authorized_for_preview": True,
            "allowed_for_customer_production": False,
            "original_file": str(path.relative_to(path.parents[1])),
            "width": 320 if avatar else 640,
            "height": 320 if avatar else 800,
        }

    def _analyse(self, root: Path, media: list[dict]):
        return BrandIdentityAnalyzer().analyze(
            run_dir=root,
            business_research={"research": {"business_name": "Example Dental"}},
            media_manifest={"media": media},
            source_url=SOURCE,
            preview=True,
        )

    def test_official_avatar_logo_is_preserved_and_drives_palette(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            logo = self._logo(root)
            green = self._graphic(root, "green.png", ((47, 166, 132), (245, 245, 245)))
            pink = self._graphic(root, "pink.png", ((237, 76, 126), (245, 245, 245)))
            green_two = self._graphic(root, "green-two.png", ((47, 166, 132), (250, 250, 250)))
            pink_two = self._graphic(root, "pink-two.png", ((237, 76, 126), (250, 250, 250)))

            identity, assets = self._analyse(root, [
                self._item(logo, "logo", avatar=True),
                self._item(green, "green-template"),
                self._item(pink, "pink-template"),
                self._item(green_two, "green-template-two"),
                self._item(pink_two, "pink-template-two"),
            ])

            self.assertEqual(identity["brand_palette_confidence"], "high")
            self.assertFalse(assets["logo"]["generatively_redrawn"])
            self.assertFalse(assets["logo"]["recoloured"])
            self.assertEqual(assets["logo"]["original_checksum"], __import__("hashlib").sha256(logo.read_bytes()).hexdigest())
            self.assertTrue((root / assets["logo"]["processed_path"]).is_file())
            self.assertTrue((root / "brand_input" / "brand_identity.md").is_file())

    def test_black_white_logo_uses_repeated_template_colours(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            logo = self._logo(root, chromatic=False)
            colours = ((38, 171, 136), (235, 63, 116))
            first = self._graphic(root, "one.png", colours)
            second = self._graphic(root, "two.png", tuple(reversed(colours)))

            identity, _assets = self._analyse(root, [
                self._item(logo, "logo", avatar=True),
                self._item(first, "template-one"),
                self._item(second, "template-two"),
            ])

            self.assertEqual(identity["brand_palette_confidence"], "medium")
            self.assertIn("black/white logo fallback", identity["palette"]["brand_primary"]["source"])

    def test_low_confidence_analysis_uses_conservative_neutral_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            logo = self._logo(root, chromatic=False)
            one = self._graphic(root, "one.png", ((180, 30, 30),))
            two = self._graphic(root, "two.png", ((30, 30, 180),))

            identity, _assets = self._analyse(root, [
                self._item(logo, "logo", avatar=True),
                self._item(one, "photo-one"),
                self._item(two, "photo-two"),
            ])

            self.assertEqual(identity["brand_palette_confidence"], "low")
            self.assertEqual(identity["palette"]["brand_background"]["hex"], "#FFFFFF")

    def test_platform_assets_are_excluded_from_brand_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            logo = self._logo(root)
            platform = self._graphic(root, "platform.png", ((35, 95, 220),))

            _identity, assets = self._analyse(root, [
                self._item(logo, "logo", avatar=True),
                self._item(platform, "meta-vr", platform=True),
            ])

            self.assertIn("meta-vr", assets["excluded_platform_asset_ids"])
            self.assertNotIn("meta-vr", assets["analysed_media_asset_ids"])

    def test_profile_photo_is_not_promoted_to_official_logo(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            originals = root / "media_input" / "originals"
            originals.mkdir(parents=True)
            portrait = originals / "portrait.png"
            image = Image.new("RGB", (320, 320))
            pixels = image.load()
            for y in range(320):
                for x in range(320):
                    pixels[x, y] = ((x * 5 + y * 3) % 256, (x * 2 + y * 7) % 256, (x * 11 + y) % 256)
            ImageDraw.Draw(image).ellipse((85, 45, 245, 265), fill=(196, 126, 92))
            image.save(portrait)

            identity, assets = self._analyse(root, [self._item(portrait, "portrait", avatar=True)])

            self.assertFalse(assets["logo"]["available"])
            self.assertEqual(assets["logo"]["confidence"], "low")
            self.assertNotEqual(identity["confidence"], "high")

    def test_simple_white_background_headshot_is_not_promoted_to_logo(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            originals = root / "media_input" / "originals"
            originals.mkdir(parents=True)
            portrait = originals / "headshot.png"
            image = Image.new("RGB", (320, 320), "white")
            draw = ImageDraw.Draw(image)
            draw.ellipse((105, 42, 215, 152), fill=(196, 126, 92))
            draw.polygon(((65, 300), (105, 145), (215, 145), (255, 300)), fill=(35, 55, 90))
            image.save(portrait)

            _identity, assets = self._analyse(root, [self._item(portrait, "headshot", avatar=True)])

            self.assertFalse(assets["logo"]["available"])

    def test_no_logo_fallback_blocks_invented_visual_mark(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            originals = root / "media_input" / "originals"
            originals.mkdir(parents=True)
            portrait = originals / "portrait.png"
            Image.new("RGB", (320, 320), (170, 120, 90)).save(portrait)
            identity, assets = BrandIdentityAnalyzer().analyze(
                run_dir=root,
                business_research={"research": {"business_name": "Plain Business"}},
                media_manifest={"media": [self._item(portrait, "portrait", avatar=True)]},
                source_url="https://instagram.com/plain_business",
                preview=True,
            )
            self.assertFalse(assets["logo"]["available"])
            self.assertEqual(identity["brand_palette_confidence"], "low")
            site = root / "site"
            screens = root / "screens"
            site.mkdir()
            screens.mkdir()
            (site / "index.html").write_text(
                '<nav><span class="badge">★</span><span>Plain Business</span></nav>',
                encoding="utf-8",
            )
            (site / "styles.css").write_text(".badge{border-radius:50%}", encoding="utf-8")
            for name in ("desktop.png", "tablet.png", "mobile.png"):
                Image.new("RGB", (320, 480), "white").save(screens / name)

            report = BrandFidelityAuditor().audit(
                brand_identity=identity,
                brand_assets_manifest=assets,
                site_dir=site,
                screenshots_dir=screens,
                preview=True,
            )
            self.assertFalse(report["approved"])
            self.assertTrue(report["no_logo_identity_violations"])

    def test_brand_package_contains_no_category_or_business_hardcoding(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            logo = self._logo(root, chromatic=False)
            identity, _assets = BrandIdentityAnalyzer().analyze(
                run_dir=root,
                business_research={"research": {"business_name": "North Star Bakery"}},
                media_manifest={"media": [self._item(logo, "logo", avatar=True)]},
                source_url="https://instagram.com/north_star_bakery",
                preview=True,
            )
            serialized = json.dumps(identity, ensure_ascii=False).lower()
            self.assertNotIn("amidental", serialized)
            self.assertNotIn("generic dental", serialized)
            self.assertNotIn("tooth silhouette", serialized)
            self.assertNotIn("clinic identity", serialized)

    def test_brand_cache_is_bound_to_research_media_and_delivery_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            logo = self._logo(root)
            business = {"research": {"business_name": "Example Dental"}}
            manifest = {"media": [self._item(logo, "logo", avatar=True)]}
            identity, assets = BrandIdentityAnalyzer().analyze(
                run_dir=root,
                business_research=business,
                media_manifest=manifest,
                source_url=SOURCE,
                preview=True,
            )
            self.assertTrue(SiteAgentOrchestrator._brand_package_valid(
                run_dir=root,
                brand_identity=identity,
                brand_assets_manifest=assets,
                source_url=SOURCE,
                business_research=business,
                media_manifest=manifest,
                preview=True,
            ))
            modified = json.loads(json.dumps(manifest))
            modified["media"][0]["allowed_for_customer_production"] = True
            self.assertFalse(SiteAgentOrchestrator._brand_package_valid(
                run_dir=root,
                brand_identity=identity,
                brand_assets_manifest=assets,
                source_url=SOURCE,
                business_research=business,
                media_manifest=modified,
                preview=True,
            ))
            self.assertFalse(SiteAgentOrchestrator._brand_package_valid(
                run_dir=root,
                brand_identity=identity,
                brand_assets_manifest=assets,
                source_url=SOURCE,
                business_research=business,
                media_manifest=manifest,
                preview=False,
            ))

    def test_brand_fidelity_requires_checksum_matched_rendered_logo_and_palette(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            logo = self._logo(root, chromatic=False)
            identity, assets = self._analyse(root, [self._item(logo, "logo", avatar=True)])
            site = root / "site"
            screenshots = root / "screens"
            (site / "assets").mkdir(parents=True)
            screenshots.mkdir()
            copied = site / "assets" / "logo.png"
            shutil.copy2(root / assets["logo"]["processed_path"], copied)
            primary = identity["palette"]["brand_primary"]["hex"]
            secondary = identity["palette"]["brand_secondary"]["hex"]
            (site / "index.html").write_text('<img src="assets/logo.png" alt="Example Dental">', encoding="utf-8")
            (site / "styles.css").write_text(f":root{{--brand-primary:{primary};--brand-secondary:{secondary};}}", encoding="utf-8")
            primary_rgb = tuple(identity["palette"]["brand_primary"]["rgb"].values())
            secondary_rgb = tuple(identity["palette"]["brand_secondary"]["rgb"].values())
            for name in ("desktop.png", "tablet.png", "mobile.png"):
                screenshot = Image.new("RGB", (320, 480), "white")
                draw = ImageDraw.Draw(screenshot)
                draw.rectangle((0, 0, 160, 120), fill=primary_rgb)
                draw.rectangle((160, 0, 320, 120), fill=secondary_rgb)
                with Image.open(root / assets["logo"]["processed_path"]) as logo_image:
                    rendered_logo = logo_image.convert("RGB")
                    rendered_logo.thumbnail((120, 110))
                    screenshot.paste(rendered_logo, (10, 10))
                screenshot.save(screenshots / name)

            report = BrandFidelityAuditor().audit(
                brand_identity=identity,
                brand_assets_manifest=assets,
                site_dir=site,
                screenshots_dir=screenshots,
                preview=True,
            )
            self.assertTrue(report["approved"])

            (site / "index.html").write_text(
                '<style>.brand{display:none}</style><img class="brand" src="assets/logo.png" alt="Example Dental">',
                encoding="utf-8",
            )
            hidden = BrandFidelityAuditor().audit(
                brand_identity=identity,
                brand_assets_manifest=assets,
                site_dir=site,
                screenshots_dir=screenshots,
                preview=True,
            )
            self.assertFalse(hidden["approved"])

            (site / "index.html").write_text('<span class="fake-logo">E</span>', encoding="utf-8")
            blocked = BrandFidelityAuditor().audit(
                brand_identity=identity,
                brand_assets_manifest=assets,
                site_dir=site,
                screenshots_dir=screenshots,
                preview=True,
            )
            self.assertFalse(blocked["approved"])

    def test_logo_matcher_preserves_visible_header_scale_on_long_full_page_screenshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            logo = self._logo(root, chromatic=False)
            screenshot_path = root / "long-mobile.png"
            screenshot = Image.new("RGB", (390, 6000), "white")
            with Image.open(logo) as opened:
                rendered = opened.convert("RGB")
                rendered.thumbnail((120, 110))
            screenshot.paste(rendered, (16, 16))
            screenshot.save(screenshot_path)
            self.assertTrue(BrandFidelityAuditor._logo_visible_in_screenshot(screenshot_path, logo))


if __name__ == "__main__":
    unittest.main()
