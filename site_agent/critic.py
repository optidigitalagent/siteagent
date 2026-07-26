from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse
from typing import TYPE_CHECKING

from playwright.sync_api import Error, sync_playwright

from site_agent.models import CritiqueReport, ResearchBrief, SiteSpec, StrategyBrief, TechnicalGate
from site_agent.design_quality import EvidenceAssessment, assess_studio_readiness
from site_agent import prompts

if TYPE_CHECKING:
    from site_agent.llm import LLMClient


class TechnicalInspector:
    def __init__(self, *, viewport_profile: str = "standard") -> None:
        if viewport_profile not in {"standard", "refinement"}:
            raise ValueError("viewport_profile must be standard or refinement")
        self.viewport_profile = viewport_profile

    def inspect(self, index_path: Path, artifacts_dir: Path) -> tuple[TechnicalGate, dict[str, str]]:
        resolved = index_path.resolve()
        return self._inspect_url(
            resolved.as_uri(), artifacts_dir, allowed_file_root=resolved.parent
        )

    def inspect_url(self, url: str, artifacts_dir: Path, *,
                    allowed_file_root: Path | None = None) -> tuple[TechnicalGate, dict[str, str]]:
        """Inspect a live HTTPS deployment using the same desktop/mobile gate as local builds."""
        if not url.startswith(("https://", "http://", "file://")):
            raise ValueError("Inspection target must be an http(s) URL or file URI.")
        return self._inspect_url(url, artifacts_dir, allowed_file_root=allowed_file_root)

    def _inspect_url(self, url: str, artifacts_dir: Path, *,
                     allowed_file_root: Path | None = None) -> tuple[TechnicalGate, dict[str, str]]:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        console_errors: list[str] = []
        failed_network_requests: list[str] = []
        observations: dict[str, str] = {}
        actual_url = url

        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                profiles = [
                    ("desktop_1440", "desktop.png", 1440, 1100, False),
                    ("tablet_768", "tablet.png", 768, 1024, True),
                    ("mobile_390", "mobile.png", 390, 844, True),
                ]
                if self.viewport_profile == "refinement":
                    profiles[1:1] = [("desktop_1024", "desktop_1024.png", 1024, 900, False)]
                    profiles.append(("mobile_360", "mobile_360.png", 360, 800, True))
                metrics_by_profile: dict[str, dict] = {}
                for profile, filename, width, height, is_mobile in profiles:
                    page_options = {
                        "viewport": {"width": width, "height": height},
                        "is_mobile": is_mobile,
                    }
                    if self.viewport_profile == "refinement":
                        page_options["service_workers"] = "block"
                    page = browser.new_page(**page_options)
                    guard = (self._install_refinement_network_guard(
                        page, url, allowed_file_root=allowed_file_root
                    )
                             if self.viewport_profile == "refinement" else None)
                    page.on(
                        "console",
                        lambda msg: console_errors.append(msg.text)
                        if msg.type == "error" else None,
                    )
                    self._watch_network(page, failed_network_requests)
                    if self.viewport_profile == "refinement":
                        page.goto(url, wait_until="domcontentloaded", timeout=15000)
                        page.wait_for_timeout(250)
                    else:
                        page.goto(url, wait_until="networkidle")
                    actual_url = page.url
                    if self.viewport_profile == "refinement":
                        expected, final = urlparse(url), urlparse(page.url)
                        if (expected.scheme in {"http", "https"}
                                and expected.hostname in {"localhost", "127.0.0.1"}
                                and (final.hostname not in {"localhost", "127.0.0.1"}
                                     or final.netloc != expected.netloc)):
                            raise ValueError("Refinement browser target redirected outside localhost.")
                    self._take_screenshot(page, artifacts_dir / filename)
                    metrics = self._collect_metrics(page)
                    metrics["actualUrl"] = page.url
                    if self.viewport_profile == "refinement":
                        metrics["brokenLinks"] = list(dict.fromkeys(
                            metrics["brokenLinks"] + self._verify_link_destinations(
                                page, url, allowed_file_root=allowed_file_root
                            )
                        ))
                        metrics["interactionChecks"] = self._exercise_interactions(page, guard)
                        metrics["interactionActualUrl"] = page.url
                        self._take_screenshot(
                            page, artifacts_dir / f"interaction_{profile}.png"
                        )
                    else:
                        metrics["interactionChecks"] = {
                            "passed": True, "checked": [], "issues": [],
                            "networkWritesPrevented": [],
                        }
                    metrics_by_profile[profile] = metrics
                    if guard is not None:
                        guard["block_all"] = True
                        self._close_refinement_page(page, guard)
                        metrics["interactionChecks"]["networkWritesPrevented"] = guard["blocked"]
                    else:
                        page.close()
                    observations[profile] = json.dumps(metrics, ensure_ascii=False, indent=2)
                reduced_metrics = {
                    "reducedMotionRequested": True, "runningAnimations": 0,
                }
                if self.viewport_profile == "refinement":
                    reduced = browser.new_page(
                        viewport={"width": 390, "height": 844},
                        is_mobile=True,
                        reduced_motion="reduce",
                        service_workers="block",
                    )
                    reduced_guard = self._install_refinement_network_guard(
                        reduced, url, allowed_file_root=allowed_file_root
                    )
                    reduced.on(
                        "console",
                        lambda msg: console_errors.append(msg.text)
                        if msg.type == "error" else None,
                    )
                    self._watch_network(reduced, failed_network_requests)
                    reduced.goto(url, wait_until="domcontentloaded", timeout=15000)
                    reduced.wait_for_timeout(250)
                    actual_url = reduced.url
                    expected, final = urlparse(url), urlparse(reduced.url)
                    if (expected.scheme in {"http", "https"}
                            and expected.hostname in {"localhost", "127.0.0.1"}
                            and (final.hostname not in {"localhost", "127.0.0.1"}
                                 or final.netloc != expected.netloc)):
                        raise ValueError("Refinement browser target redirected outside localhost.")
                    self._take_screenshot(reduced, artifacts_dir / "reduced_motion.png")
                    reduced_metrics = reduced.evaluate(
                        """() => ({
                          viewport: `${window.innerWidth}x${window.innerHeight}`,
                          reducedMotionRequested: matchMedia('(prefers-reduced-motion: reduce)').matches,
                          runningAnimations: document.getAnimations().filter(animation =>
                            animation.playState === 'running' &&
                            Number(animation.effect?.getTiming?.().duration || 0) > 0
                          ).length
                        })"""
                    )
                    reduced_metrics["actualUrl"] = reduced.url
                    reduced_guard["block_all"] = True
                    self._close_refinement_page(reduced, reduced_guard)
                    if reduced_guard["initial_issues"]:
                        reduced_metrics["lifecycleSafetyIssues"] = list(
                            dict.fromkeys(reduced_guard["initial_issues"])
                        )
                    observations["reduced_motion"] = json.dumps(
                        reduced_metrics, ensure_ascii=False, indent=2
                    )
                # Backward-compatible aliases keep the existing BUILD critic
                # contract stable while refinement consumes all five widths.
                observations["desktop"] = observations["desktop_1440"]
                observations["tablet"] = observations["tablet_768"]
                observations["mobile"] = observations["mobile_390"]
            finally:
                browser.close()

        def combined(name: str) -> list[str]:
            return list(dict.fromkeys(
                item for metrics in metrics_by_profile.values() for item in metrics[name]
            ))

        missing_images = combined("missingImages")
        broken_links = combined("brokenLinks")
        small_tap_targets = combined("smallTapTargets")
        persistent_header_issues = combined("persistentHeaderIssues")
        footer_issues = combined("footerIssues")
        clipped_primary_ctas = combined("clippedPrimaryCtas")
        functional_issues = list(dict.fromkeys(
            issue for metrics in metrics_by_profile.values()
            for issue in metrics["interactionChecks"]["issues"]
        ))
        reduced_motion_issues = []
        if not reduced_metrics["reducedMotionRequested"]:
            reduced_motion_issues.append("Browser did not activate prefers-reduced-motion: reduce.")
        if reduced_metrics["runningAnimations"]:
            reduced_motion_issues.append(
                f"{reduced_metrics['runningAnimations']} animation(s) still run under reduced motion."
            )
        reduced_motion_issues.extend(reduced_metrics.get("lifecycleSafetyIssues", []))
        horizontal_scroll = any(metrics["horizontalScroll"] for metrics in metrics_by_profile.values())
        failed_network_requests = list(dict.fromkeys(failed_network_requests))
        gate = TechnicalGate(
            passed=not (
                horizontal_scroll
                or missing_images
                or console_errors
                or failed_network_requests
                or broken_links
                or small_tap_targets
                or persistent_header_issues
                or footer_issues
                or clipped_primary_ctas
                or functional_issues
                or reduced_motion_issues
            ),
            horizontal_scroll=horizontal_scroll,
            missing_images=missing_images,
            console_errors=console_errors,
            failed_network_requests=failed_network_requests,
            broken_links=broken_links,
            small_tap_targets=small_tap_targets,
            persistent_header_issues=persistent_header_issues,
            footer_issues=footer_issues,
            clipped_primary_ctas=clipped_primary_ctas,
            functional_issues=functional_issues,
            reduced_motion_issues=reduced_motion_issues,
            notes=[f"{profile}: {metrics['viewport']}"
                   for profile, metrics in metrics_by_profile.items()],
        )
        (artifacts_dir / "technical_gate.json").write_text(
            gate.model_dump_json(indent=2), encoding="utf-8"
        )
        (artifacts_dir / "observations.json").write_text(
            json.dumps({"url": actual_url, **observations}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return gate, observations

    @staticmethod
    def _install_refinement_network_guard(
        page, expected_url: str, *, allowed_file_root: Path | None = None,
    ) -> dict:
        """Install a fail-closed guard before navigation and retain it through unload."""
        expected = urlparse(expected_url)
        file_root = allowed_file_root.resolve() if allowed_file_root else None
        if expected.scheme == "file" and file_root is None:
            expected_path = Path(unquote(
                expected.path.lstrip("/") if os.name == "nt" else expected.path
            )).resolve()
            file_root = expected_path.parent
        guard: dict = {"block_all": False, "blocked": [], "initial_issues": []}

        def record(method: str, url: str) -> None:
            phase = "interaction" if guard["block_all"] else "initial-load"
            item = {"method": method, "url": url, "phase": phase}
            guard["blocked"].append(item)
            if phase == "initial-load":
                guard["initial_issues"].append(
                    f"Blocked {method} network side effect during refinement page load: {url}"
                )

        def neutralize_network(route) -> None:
            request = route.request
            parsed = urlparse(request.url)
            same_local_origin = (
                expected.scheme in {"http", "https"}
                and expected.hostname in {"localhost", "127.0.0.1"}
                and parsed.netloc == expected.netloc
                and parsed.hostname in {"localhost", "127.0.0.1"}
            )
            safe_file_read = False
            if parsed.scheme == "file" and file_root is not None:
                requested_path = Path(unquote(
                    parsed.path.lstrip("/") if os.name == "nt" else parsed.path
                )).resolve()
                safe_file_read = (
                    requested_path == file_root or file_root in requested_path.parents
                )
            safe_initial_read = (
                not guard["block_all"]
                and request.method in {"GET", "HEAD", "OPTIONS"}
                and (safe_file_read or same_local_origin)
            )
            if safe_initial_read:
                route.continue_()
                return
            method = "BEACON" if request.resource_type == "ping" else request.method
            record(method, request.url)
            route.fulfill(
                status=503,
                content_type="application/json",
                body='{"ok":false,"siteagent_qa":"network_neutralized"}',
            )

        def neutralize_websocket(socket) -> None:
            record("WEBSOCKET", socket.url)
            # Not calling connect_to_server keeps this as an in-browser mock;
            # swallowing client messages guarantees no external socket exists.
            socket.on_message(lambda message: None)

        def close_popup(popup) -> None:
            record("POPUP", popup.url)
            popup.close()

        page.add_init_script(
            """(() => {
              window.__siteagentQaBlocked = [];
              window.__siteagentQaBlockAll = false;
              const record = (method, url) => window.__siteagentQaBlocked.push({
                method, url: String(url || ''),
                phase: window.__siteagentQaBlockAll ? 'interaction' : 'initial-load'
              });
              window.open = (url, ...args) => { record('POPUP', url); return null; };
              class BlockedWebSocket extends EventTarget {
                static CONNECTING = 0; static OPEN = 1; static CLOSING = 2; static CLOSED = 3;
                constructor(url, protocols) {
                  super(); this.url = String(url); this.readyState = 3;
                  this.protocol = ''; this.extensions = ''; this.bufferedAmount = 0;
                  this.binaryType = 'blob'; record('WEBSOCKET', url);
                  queueMicrotask(() => {
                    this.dispatchEvent(new Event('error'));
                    this.dispatchEvent(new CloseEvent('close', {code:1008, reason:'QA blocked'}));
                  });
                }
                send(data) { record('WEBSOCKET_SEND', this.url); }
                close() { this.readyState = 3; }
              }
              window.WebSocket = BlockedWebSocket;
            })()"""
        )
        page.context.route("**/*", neutralize_network)
        page.context.route_web_socket("**/*", neutralize_websocket)
        page.on("popup", close_popup)
        return guard

    @staticmethod
    def _drain_page_blocks(page, guard: dict) -> None:
        try:
            items = page.evaluate(
                "() => window.__siteagentQaBlocked?.splice(0) || []"
            )
        except Exception:
            items = []
        for item in items:
            guard["blocked"].append(item)
            if item.get("phase") == "initial-load":
                guard["initial_issues"].append(
                    f"Blocked {item.get('method')} network side effect during "
                    f"refinement page load: {item.get('url')}"
                )

    @classmethod
    def _close_refinement_page(cls, page, guard: dict) -> None:
        """Exercise synthetic states and a real unload under the active guard."""
        try:
            page.evaluate(
                """() => {
                  window.__siteagentQaBlockAll = true;
                  window.dispatchEvent(new PageTransitionEvent('pagehide', {persisted:false}));
                  window.dispatchEvent(new Event('beforeunload', {cancelable:true}));
                }"""
            )
            page.wait_for_timeout(50)
            cls._drain_page_blocks(page, guard)
            # A real same-context navigation executes unload/pagehide handlers.
            # about:blank performs no external request and keeps the guard active.
            page.goto("about:blank", wait_until="commit", timeout=5000)
            page.wait_for_timeout(100)
        finally:
            page.close(run_before_unload=False)

    @staticmethod
    def _exercise_interactions(page, guard: dict | None = None) -> dict:
        """Exercise generic interactions without allowing network side effects."""
        if guard is None:
            raise ValueError("Refinement interactions require a pre-navigation network guard.")
        guard["block_all"] = True
        page.evaluate("() => { window.__siteagentQaBlockAll = true; }")
        result = page.evaluate(
            """async () => {
              const issues = [];
              const checked = [];
              const visible = element => Boolean(element && element.getClientRects().length &&
                getComputedStyle(element).visibility !== 'hidden' &&
                getComputedStyle(element).display !== 'none');
              const bounded = (elements, limit, label) => {
                if (elements.length > limit) {
                  issues.push(`${label} count ${elements.length} exceeds safe QA bound ${limit}.`);
                }
                return elements.slice(0, limit);
              };
              for (const control of bounded(Array.from(document.querySelectorAll('[aria-controls][aria-expanded]')), 8, 'Disclosure')) {
                if (!visible(control)) continue;
                const target = document.getElementById(control.getAttribute('aria-controls'));
                const before = control.getAttribute('aria-expanded');
                control.click();
                await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
                const after = control.getAttribute('aria-expanded');
                checked.push(`disclosure:${control.getAttribute('aria-controls')}`);
                if (before === after || !target || (after === 'true' && !visible(target))) {
                  issues.push(`Disclosure control failed: ${control.getAttribute('aria-controls') || control.textContent.trim()}`);
                }
                control.click();
              }
              for (const details of bounded(Array.from(document.querySelectorAll('details')), 8, 'Details/accordion')) {
                const summary = details.querySelector('summary');
                if (!summary || !visible(summary)) continue;
                const before = details.open;
                summary.click();
                checked.push('details');
                if (details.open === before) issues.push('Details/accordion did not toggle.');
                summary.click();
              }
              for (const tab of bounded(Array.from(document.querySelectorAll('[role="tab"]')), 8, 'Tab')) {
                if (!visible(tab)) continue;
                tab.click();
                await new Promise(resolve => requestAnimationFrame(resolve));
                checked.push('tab');
                if (tab.getAttribute('aria-selected') !== 'true') {
                  issues.push(`Tab did not become selected: ${tab.textContent.trim()}`);
                }
              }
              for (const form of bounded(Array.from(document.forms), 4, 'Form')) {
                const feedbackSelector = '[role="status"], [role="alert"], [data-form-success], [data-form-error], .form-success, .form-error';
                const feedbackBefore = Array.from(form.querySelectorAll(feedbackSelector)).map(node => ({
                  node, visible: visible(node), text: (node.textContent || '').trim()
                }));
                checked.push('form-invalid');
                if (!form.checkValidity()) {
                  form.reportValidity();
                  if (!form.contains(document.activeElement)) {
                    issues.push('Invalid form did not focus a field in the form.');
                  }
                }
                const original = Array.from(form.elements).map(control => [control, control.value, control.checked]);
                for (const control of Array.from(form.elements)) {
                  if (!control.required || control.disabled || control.value) continue;
                  if (control.type === 'email') control.value = 'qa@example.test';
                  else if (control.type === 'url') control.value = 'https://example.test/';
                  else if (control.type === 'tel') control.value = '+15555550123';
                  else if (control.type === 'checkbox' || control.type === 'radio') control.checked = true;
                  else control.value = 'SiteAgent QA';
                }
                checked.push('form-valid');
                if (!form.checkValidity()) issues.push('Form cannot reach a valid input state.');
                const action = form.getAttribute('action') || '';
                const event = new Event('submit', {bubbles: true, cancelable: true});
                form.dispatchEvent(event);
                await new Promise(resolve => setTimeout(resolve, 100));
                const changedVisibleFeedback = Array.from(form.querySelectorAll(feedbackSelector)).some(node => {
                  if (!visible(node)) return false;
                  const before = feedbackBefore.find(item => item.node === node);
                  const text = (node.textContent || '').trim();
                  return !before || !before.visible || before.text !== text;
                });
                const fallback = /^(mailto|tel|sms|whatsapp|tg):/i.test(action);
                if (event.defaultPrevented && !changedVisibleFeedback) {
                  issues.push('Handled form submission did not expose a new visible success or error state.');
                } else if (!event.defaultPrevented && !fallback) {
                  issues.push('Form outcome is unverified: use a safe contact fallback or expose a visible handled status state.');
                }
                for (const [control, value, checked] of original) {
                  control.value = value;
                  if ('checked' in control) control.checked = checked;
                }
              }
              for (const opener of bounded(Array.from(document.querySelectorAll('[aria-haspopup="dialog"], [data-modal-target]')), 4, 'Dialog opener')) {
                if (!visible(opener)) continue;
                opener.click();
                await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
                checked.push('modal');
                const dialog = document.querySelector('dialog[open], [role="dialog"]:not([hidden])');
                if (!visible(dialog)) issues.push('Modal/dialog opener did not reveal a dialog.');
                const close = dialog?.querySelector('[data-close], [aria-label*="close" i], button');
                if (close) close.click();
              }
              for (const slider of bounded(Array.from(document.querySelectorAll('input[type="range"], [role="slider"]')), 4, 'Slider')) {
                if (!visible(slider)) continue;
                checked.push('slider');
                if (slider.matches('input[type="range"]')) {
                  const before = slider.value;
                  slider.value = String(Number(before || slider.min || 0) + 1);
                  slider.dispatchEvent(new Event('input', {bubbles: true}));
                  if (slider.value === before) issues.push('Slider value did not change.');
                }
              }
              for (const video of bounded(Array.from(document.querySelectorAll('video')), 4, 'Video')) {
                checked.push('video');
                if (video.error || video.networkState === HTMLMediaElement.NETWORK_NO_SOURCE) {
                  issues.push('Video has no playable source.');
                }
              }
              return {passed: issues.length === 0, checked, issues};
            }"""
        )
        TechnicalInspector._drain_page_blocks(page, guard)
        result["issues"] = list(dict.fromkeys(
            result["issues"] + guard["initial_issues"]
        ))
        result["passed"] = not result["issues"]
        result["networkWritesPrevented"] = guard["blocked"]
        return result

    @staticmethod
    def _verify_link_destinations(
        page, current_url: str, *, allowed_file_root: Path | None = None,
    ) -> list[str]:
        hrefs = page.eval_on_selector_all(
            "a[href]", "elements => elements.map(element => element.getAttribute('href'))"
        )
        failures = []
        current = urlparse(current_url)
        file_root = allowed_file_root.resolve() if allowed_file_root else None
        if current.scheme == "file" and file_root is None:
            current_path = Path(unquote(
                current.path.lstrip("/") if os.name == "nt" else current.path
            )).resolve()
            file_root = current_path.parent
        for href in dict.fromkeys(value for value in hrefs if value):
            if href.startswith("mailto:"):
                address = href[7:].split("?", 1)[0].strip()
                if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", address):
                    failures.append(f"Invalid email destination: {href}")
                continue
            if href.startswith(("tel:", "sms:")):
                digits = re.sub(r"\D", "", href.split(":", 1)[1].split("?", 1)[0])
                if len(digits) < 7:
                    failures.append(f"Invalid phone destination: {href}")
                continue
            if href.startswith(("whatsapp:", "tg:")):
                if not href.split(":", 1)[1].strip("/ ?"):
                    failures.append(f"Invalid messenger destination: {href}")
                continue
            if href.startswith("#"):
                if href != "#" and not page.locator(href).count():
                    failures.append(f"Missing anchor target: {href}")
                continue
            resolved = urlparse(urljoin(current_url, href))
            if resolved.scheme == "file":
                path = Path(unquote(
                    resolved.path.lstrip("/") if os.name == "nt" else resolved.path
                )).resolve()
                if (file_root is not None and path != file_root
                        and file_root not in path.parents):
                    failures.append(f"Local destination escapes the project: {href}")
                elif not path.is_file():
                    failures.append(f"Missing local destination: {href}")
            elif resolved.scheme in {"http", "https"} and resolved.netloc == current.netloc:
                if resolved.username or resolved.password or not resolved.path.startswith("/"):
                    failures.append(f"Invalid internal destination: {href}")
        return failures

    def _take_screenshot(self, page, path: Path) -> None:
        """Retry a transient Chromium capture failure before failing the quality gate."""
        # Chromium's full-page capture does not always paint below-fold lazy
        # media in a file:// review. Traverse the page once so screenshot-led
        # criticism sees the same authorised proof a visitor can scroll to.
        page.evaluate(
            """async () => {
              // Ask Chromium to fetch every authorised image before walking
              // the page. A pending lazy image is not a broken image, and a
              // full-page screenshot alone does not reliably activate it.
              for (const image of Array.from(document.images)) {
                image.loading = "eager";
                if (!image.src && image.dataset.src) image.src = image.dataset.src;
                if (!image.srcset && image.dataset.srcset) image.srcset = image.dataset.srcset;
              }
              const max = Math.max(document.documentElement.scrollHeight, document.body.scrollHeight);
              const step = Math.max(window.innerHeight * 0.8, 320);
              for (let y = 0; y < max; y += step) {
                window.scrollTo(0, y);
                await new Promise(resolve => setTimeout(resolve, 35));
              }
              await Promise.all(Array.from(document.images).map(image => image.complete
                ? Promise.resolve()
                : Promise.race([
                    new Promise(resolve => {
                      image.addEventListener('load', resolve, {once: true});
                      image.addEventListener('error', resolve, {once: true});
                    }),
                    new Promise(resolve => setTimeout(resolve, 5000)),
                  ])
              ));
              await Promise.all(Array.from(document.images).map(image =>
                image.complete && image.naturalWidth > 0 && image.decode
                  ? image.decode().catch(() => undefined)
                  : Promise.resolve()
              ));
              window.scrollTo(0, 0);
              await new Promise(resolve => setTimeout(resolve, 120));
            }"""
        )
        last_error: Error | None = None
        for attempt in range(3):
            try:
                page.screenshot(path=path, full_page=True)
                return
            except Error as exc:
                last_error = exc
                if attempt == 2:
                    break
                page.wait_for_timeout(250 * (attempt + 1))
        assert last_error is not None
        raise last_error

    def _watch_network(self, page, failures: list[str]) -> None:
        page.on(
            "requestfailed",
            lambda request: failures.append(
                f"{request.method} {request.url} ({request.failure or 'request failed'})"
            ),
        )
        page.on(
            "response",
            lambda response: failures.append(
                f"{response.status} {response.request.method} {response.url}"
            )
            if response.status >= 400
            else None,
        )

    def _collect_metrics(self, page):
        return page.evaluate(
            """
            async () => {
              const doc = document.documentElement;
              const body = document.body;
              const horizontalScroll = doc.scrollWidth > doc.clientWidth + 1 || body.scrollWidth > body.clientWidth + 1;
              const missingImages = Array.from(document.images)
                // `complete === false` means the request is still pending. It
                // is not evidence of a missing asset; request failures are
                // independently captured by the network watcher above.
                .filter(img => img.complete && img.naturalWidth === 0)
                .map(img => img.currentSrc || img.src || img.alt || "unknown image");
              const brokenLinks = Array.from(document.querySelectorAll("a[href]"))
                .map(a => a.getAttribute("href"))
                .filter(href => !href || href === "#" || href.startsWith("javascript:"));
              const smallTapTargets = Array.from(document.querySelectorAll("a, button"))
                .filter(el => {
                  const style = window.getComputedStyle(el);
                  if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) return false;
                  // Controls inside a hidden ancestor have their own computed
                  // display value but no rendered box. They are not currently
                  // interactive and must not be reported as 0x0 tap targets.
                  if (el.getClientRects().length === 0) return false;
                  const r = el.getBoundingClientRect();
                  return r.width < 44 || r.height < 44;
                })
                .map(el => (el.textContent || el.getAttribute("aria-label") || el.tagName).trim().slice(0, 80));
              const persistentHeaderIssues = [];
              const header = document.querySelector("header");
              if (!header) {
                persistentHeaderIssues.push("Page has no header landmark.");
              } else {
                const style = window.getComputedStyle(header);
                if (!['sticky', 'fixed'].includes(style.position) || style.top === 'auto') {
                  persistentHeaderIssues.push(`Header is not persistent (position: ${style.position}; top: ${style.top}).`);
                } else {
                  const originalY = window.scrollY;
                  const available = Math.max(0, doc.scrollHeight - window.innerHeight);
                  const targetY = Math.min(640, available);
                  if (targetY > 32) {
                    window.scrollTo(0, targetY);
                    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
                    const top = header.getBoundingClientRect().top;
                    if (Math.abs(top) > 2) persistentHeaderIssues.push(`Header leaves the viewport after scroll (top: ${top.toFixed(1)}px).`);
                    window.scrollTo(0, originalY);
                    await new Promise(resolve => requestAnimationFrame(resolve));
                  }
                }
              }
              const footerIssues = [];
              const footer = document.querySelector("footer");
              if (!footer) {
                footerIssues.push("Page has no footer landmark.");
              } else {
                const footerNavigation = footer.querySelector("nav");
                const footerNavigationLinks = footerNavigation
                  ? Array.from(footerNavigation.querySelectorAll("a[href]")).filter(link => link.getAttribute("href")).length
                  : 0;
                if (!footerNavigation || footerNavigationLinks < 2) {
                  footerIssues.push("Footer lacks a usable navigation group with at least two destinations.");
                }
                const footerCta = footer.querySelector("[data-site-cta='primary'], a[href*='contact'], a[href*='book'], a[href^='mailto:'], a[href^='tel:'], form button[type='submit']");
                if (!footerCta) footerIssues.push("Footer lacks a clear conversion or contact action.");
              }
              const primaryCtas = Array.from(document.querySelectorAll("[data-site-cta='primary'], .live-cta, .btn.primary, .header-cta, [class*='primary-cta']"));
              const clippedPrimaryCtas = primaryCtas
                .filter(cta => cta.getClientRects().length > 0 && window.getComputedStyle(cta).visibility !== 'hidden')
                .filter(cta => Array.from(cta.querySelectorAll("*")).some(part => {
                  if (!(part.textContent || '').trim() || part.getClientRects().length === 0) return false;
                  return part.scrollWidth > part.clientWidth + 1 || part.scrollHeight > part.clientHeight + 1;
                }))
                .map(cta => (cta.textContent || cta.getAttribute("aria-label") || "primary CTA").replace(/\\s+/g, " ").trim().slice(0, 80));
              const headings = Array.from(document.querySelectorAll("h1,h2")).map(h => h.textContent.trim());
              const buttons = Array.from(document.querySelectorAll("a.btn,button")).map(b => b.textContent.trim());
              const sectionIds = Array.from(document.querySelectorAll("main section")).map(s => s.id || s.className || "section");
              const interactions = {
                forms: document.querySelectorAll('form').length,
                menus: document.querySelectorAll('[aria-expanded], [aria-controls]').length,
                accordions: document.querySelectorAll('details, [role="button"][aria-expanded]').length,
                dialogs: document.querySelectorAll('dialog, [role="dialog"]').length,
                sliders: document.querySelectorAll('[role="slider"], input[type="range"], [data-slider]').length,
                videos: document.querySelectorAll('video, iframe[src*="youtube"], iframe[src*="vimeo"]').length,
                maps: document.querySelectorAll('[data-map], iframe[src*="google.com/maps"], iframe[src*="openstreetmap"]').length
              };
              const primaryCtaCount = primaryCtas.length;
              const contactLinkCount = document.querySelectorAll("a[href^='tel:'], a[href^='mailto:'], a[href*='wa.me'], a[href*='t.me'], a[href*='instagram.com']").length;
              const actionLinks = Array.from(document.querySelectorAll('a[href]')).map(link => ({
                href: link.getAttribute('href') || '',
                text: (link.textContent || link.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim().slice(0, 200),
                primary: primaryCtas.includes(link),
                contact: /^(mailto:|tel:|sms:|whatsapp:|tg:)/i.test(link.getAttribute('href') || '') ||
                  /(wa\\.me|t\\.me|instagram\\.com)/i.test(link.getAttribute('href') || '')
              }));
              return {
                viewport: `${window.innerWidth}x${window.innerHeight}`,
                scrollWidth: doc.scrollWidth,
                clientWidth: doc.clientWidth,
                horizontalScroll,
                missingImages,
                brokenLinks,
                smallTapTargets,
                persistentHeaderIssues,
                footerIssues,
                clippedPrimaryCtas,
                headings,
                buttons,
                interactions,
                primaryCtaCount,
                contactLinkCount,
                actionLinks,
                sectionIds,
                bodyTextSample: document.body.innerText.replace(/\\s+/g, " ").trim().slice(0, 1800),
                bodyText: document.body.innerText.trim().slice(0, 50000)
              };
            }
            """
        )


class CriticAgent:
    def __init__(self, llm: "LLMClient", inspector: TechnicalInspector | None = None) -> None:
        self.llm = llm
        self.inspector = inspector or TechnicalInspector()

    def run(
        self,
        *,
        index_path: Path,
        artifacts_dir: Path,
        research: ResearchBrief,
        strategy: StrategyBrief,
        site_spec: SiteSpec,
        evidence: EvidenceAssessment | None = None,
    ) -> CritiqueReport:
        technical_gate, observations = self.inspector.inspect(index_path, artifacts_dir)
        public_spec = self._public_site_spec(site_spec)
        scope = evidence or assess_studio_readiness(research)
        return self.llm.structured(
            system=prompts.CRITIC_SYSTEM,
            user=prompts.CRITIC_USER.format(
                research_json=research.model_dump_json(indent=2),
                strategy_json=strategy.model_dump_json(indent=2),
                site_spec_json=public_spec.model_dump_json(indent=2),
                scope_json=json.dumps({
                    "level": scope.level.value,
                    "scope": scope.page_scope.value,
                    "exact_product": scope.exact_product,
                    "required_concepts": scope.required_concepts,
                    "rules": {
                        "micro_site": "Require an offer, either evidence-grounded real proof or a verified process, and a conversion close. Never require or invent a contact sequence, call method, timing, clinical step, or process that the research does not confirm. Do not require a gallery, FAQ, team, reviews, certificates, price list, or a longer full-site path.",
                        "full_site": "Require a complete commercial path appropriate to the sourced themes and media.",
                        "blocked": "No site may be approved; evidence is insufficient for creative output.",
                    },
                }, ensure_ascii=False, indent=2),
                technical_json=technical_gate.model_dump_json(indent=2),
                desktop_observations=observations["desktop"],
                mobile_observations=observations["mobile"],
            ),
            schema=CritiqueReport,
        )

    def _public_site_spec(self, site_spec: SiteSpec) -> SiteSpec:
        public_spec = site_spec.model_copy(deep=True)
        for section in public_spec.sections:
            section.purpose = ""
        public_spec.gallery_assets = [
            asset
            for asset in public_spec.gallery_assets
            if asset.url.startswith(("http://", "https://"))
        ]
        return public_spec
