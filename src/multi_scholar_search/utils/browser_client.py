"""Browser client: DrissionPage (primary, with reCAPTCHA solver) + Playwright async fallback."""
from __future__ import annotations

import asyncio
import logging

from bs4 import BeautifulSoup
from DrissionPage import ChromiumPage, ChromiumOptions
from playwright.async_api import async_playwright

from .user_agents import get_random

log = logging.getLogger("mss.browser")


def _is_captcha(html: str) -> bool:
    lower = html.lower()
    return (
        "unusual traffic" in lower
        or "recaptcha" in lower
        or "captcha" in lower
    )


class BrowserClient:
    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self.page = None

    # ------------------------------------------------------------------
    # DrissionPage — primary (better bot evasion + reCAPTCHA solver)
    # ------------------------------------------------------------------

    def fetch_with_drission(self, url: str) -> BeautifulSoup:
        from ..config import settings
        from .recaptcha_solver import DrissionRecaptchaSolver

        options = ChromiumOptions()
        options.set_browser_path(settings.chromium_path)
        options.headless(True)
        options.set_argument("--no-sandbox")
        options.set_argument("--disable-dev-shm-usage")
        options.set_argument("--disable-blink-features=AutomationControlled")
        options.set_user_agent(get_random())

        if settings.chromium_proxy:
            options.set_proxy(settings.chromium_proxy)
            log.debug("[drission] Using proxy: %s", settings.chromium_proxy)

        driver = ChromiumPage(options)
        try:
            driver.get(url)
            driver.wait.load_start(timeout=15)
            import time as _time
            from ..config import settings as _s
            _time.sleep(_s.drission_settle_time)
            html = driver.html

            if _is_captcha(html):
                log.warning("[drission] CAPTCHA detected, attempting audio solver...")
                try:
                    solver = DrissionRecaptchaSolver(driver)
                    solver.solve()
                    driver.get(url)
                    driver.wait.load_start(timeout=15)
                    html = driver.html
                    log.info("[drission] CAPTCHA solved, page reloaded")
                except Exception as exc:
                    log.warning("[drission] CAPTCHA solver failed: %s", exc.__class__.__name__)

            return BeautifulSoup(html, "html.parser")
        finally:
            driver.quit()

    # ------------------------------------------------------------------
    # Playwright async — fallback
    # ------------------------------------------------------------------

    async def start(self) -> None:
        from ..config import settings

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            executable_path=settings.chromium_path,
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )

        context_kwargs: dict = {
            "user_agent": get_random(),
            "viewport": {"width": 1280, "height": 900},
            "locale": "en-US",
        }
        if settings.chromium_proxy:
            context_kwargs["proxy"] = {"server": settings.chromium_proxy}
            log.debug("[playwright] Using proxy: %s", settings.chromium_proxy)

        context = await self._browser.new_context(**context_kwargs)
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        self.page = await context.new_page()

    async def goto(self, url: str) -> None:
        await self.page.goto(url, wait_until="networkidle", timeout=30000)

    async def get_content(self) -> BeautifulSoup:
        html = await self.page.content()
        return BeautifulSoup(html, "html.parser")

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
