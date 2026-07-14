from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from site_agent.config import Settings
from site_agent.identifiers import stable_business_id
from site_agent.publisher import CloudflarePagesPublisher


SMOKE_URL = "https://instagram.com/siteagent-cloudflare-smoke"


@unittest.skipUnless(
    os.getenv("RUN_CLOUDFLARE_SMOKE") == "1"
    and bool(os.getenv("CLOUDFLARE_ACCOUNT_ID"))
    and bool(os.getenv("CLOUDFLARE_API_TOKEN")),
    "Set RUN_CLOUDFLARE_SMOKE=1 and local Cloudflare credentials to run.",
)
class CloudflarePagesSmokeTest(unittest.TestCase):
    def test_direct_upload_and_live_verification(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            site = Path(temp) / "site"
            site.mkdir()
            marker = stable_business_id(SMOKE_URL)
            (site / "index.html").write_text(
                "<!doctype html><html><head>"
                f'<meta name="siteagent-business-id" content="{marker}">'
                "<title>site-agent Cloudflare smoke</title>"
                "</head><body>site-agent Cloudflare smoke</body></html>",
                encoding="utf-8",
            )
            config = Settings(
                _env_file=None,
                HOSTING_PROVIDER="cloudflare_pages",
                PUBLISH_REQUIRED=True,
                CLOUDFLARE_ACCOUNT_ID=os.environ["CLOUDFLARE_ACCOUNT_ID"],
                CLOUDFLARE_API_TOKEN=os.environ["CLOUDFLARE_API_TOKEN"],
                CLOUDFLARE_PROJECT_PREFIX="siteagent-smoke",
            )
            result = CloudflarePagesPublisher(config).publish(
                site_dir=site,
                instagram_url=SMOKE_URL,
            )
            self.assertTrue(result.is_verified_production)
            print(result.production_url)


if __name__ == "__main__":
    unittest.main()
