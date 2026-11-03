"""Optional browser UI smoke tests: python tests/browser-smoke.py (requires Playwright + Chromium).

All assets are injected into an isolated browser document: no localhost service,
network access, broker connection or AI token calls are required.
"""
import asyncio
import re
from pathlib import Path
from playwright.async_api import async_playwright

SITE = Path(__file__).resolve().parents[1]

async def check(width: int, browser):
    page = await browser.new_page(viewport={"width": width, "height": 840}, device_scale_factor=1)
    page.set_default_timeout(4000)
    errors = []
    page.on("pageerror", lambda exception: errors.append(str(exception)))
    html = (SITE / "index.html").read_text(encoding="utf-8")
    html = re.sub(r'<link rel="stylesheet" href="./operator.css">', "", html)
    html = re.sub(r'<script src="./[^"]+" defer></script>', "", html)
    await page.set_content(html, wait_until="load")
    await page.add_style_tag(content=(SITE / "operator.css").read_text(encoding="utf-8"))
    await page.add_script_tag(content=(SITE / "demo-fixture.js").read_text(encoding="utf-8"))
    await page.add_script_tag(content=(SITE / "operator.js").read_text(encoding="utf-8"))
    nav = ".side-nav " if width > 800 else ".bottom-nav "
    settings_nav = ".sidebar " if width > 800 else ".bottom-nav "
    assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert await page.locator("#equity-value").inner_text() == "Unavailable"
    assert await page.locator(".mode-chip").inner_text() == "RESEARCH"
    assert await page.locator("#demo-banner").is_hidden()
    assert await page.locator(".advanced-link").count() == 6
    await page.locator(nav + 'a[data-route="markets"]').click()
    assert await page.locator(".market-row").count() == 3
    await page.locator("#market-search").fill("SOL")
    assert await page.locator(".market-row").count() == 1
    await page.locator("#market-search").fill("")
    await page.locator(settings_nav + 'a[data-route="settings"]').click()
    await page.locator("#demo-toggle").check()
    assert await page.locator("#demo-banner").is_visible()
    await page.locator(nav + 'a[data-route="home"]').click()
    assert "A$10,125.40" in await page.locator("#equity-value").inner_text()
    await page.locator(nav + 'a[data-route="activity"]').click()
    assert await page.locator(".activity-row").count() == 3
    await page.locator("#activity-filter").select_option("research")
    assert await page.locator(".activity-row").count() == 1
    await page.locator(settings_nav + 'a[data-route="settings"]').click()
    await page.locator("#demo-toggle").uncheck()
    assert await page.locator("#demo-banner").is_hidden()
    await page.locator(nav + 'a[data-route="home"]').click()
    assert await page.locator("#equity-value").inner_text() == "Unavailable"
    assert not errors, errors
    await page.close()
    print(f"Browser smoke: {width}px — PASS")

async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, executable_path="/usr/bin/chromium", args=["--no-sandbox"])
        try:
            for width in (320, 390, 1440):
                await check(width, browser)
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
