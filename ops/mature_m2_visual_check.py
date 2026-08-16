from __future__ import annotations

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    screenshot = root / "m2-dashboard-production.png"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=True,
            args=["--disable-gpu"],
        )
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        errors: list[str] = []
        page.on("console", lambda message: errors.append(
            f"console:{message.type}:{message.text}"
        ) if message.type == "error" else None)
        page.on("pageerror", lambda error: errors.append(f"page:{error}"))

        login_response = page.context.request.post(
            "http://cha.jdair.top/api/login",
            data={
                "username": os.environ["CHA_LOGIN_USER"],
                "password": os.environ["CHA_LOGIN_PASS"],
            },
            timeout=90000,
        )
        if login_response.status != 200 or not login_response.json().get("ok"):
            raise RuntimeError("visual-check login failed")

        page.goto(
            "http://cha.jdair.top/api/v2/dashboard",
            wait_until="domcontentloaded",
            timeout=90000,
        )
        page.wait_for_function(
            "() => !document.getElementById('metricDevices')?.classList.contains('skeleton')",
            timeout=90000,
        )
        page.wait_for_timeout(1500)

        values = page.evaluate(
            """() => ({
              title: document.title,
              metricDevices: document.getElementById('metricDevices')?.innerText,
              metricOnline: document.getElementById('metricOnline')?.innerText,
              metricFiles: document.getElementById('metricFiles')?.innerText,
              geoRows: document.querySelectorAll('#geoRows tr[data-city]').length,
              exceptionRows: document.querySelectorAll('#exceptionRows tr').length,
              freshnessRows: document.querySelectorAll('.freshness-row').length,
              notice: document.getElementById('notice')?.innerText || '',
              bodyWidth: document.body.scrollWidth,
              viewportWidth: window.innerWidth,
              bodyHeight: document.body.scrollHeight,
              theme: document.documentElement.dataset.theme,
              userLine: document.getElementById('userLine')?.innerText
            })"""
        )
        page.click("#themeBtn")
        page.wait_for_function(
            "() => document.documentElement.dataset.theme === 'light'"
        )
        theme_toggle = page.evaluate(
            "() => document.documentElement.dataset.theme"
        )
        page.click("#themeBtn")
        page.wait_for_function(
            "() => document.documentElement.dataset.theme === 'dark'"
        )
        page.screenshot(path=str(screenshot), full_page=True)
        browser.close()

    result = {
        "screenshot": str(screenshot),
        "screenshot_size": screenshot.stat().st_size,
        "values": values,
        "theme_toggle": theme_toggle,
        "errors": errors,
    }
    (root / "m2-visual-check.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False))
    if errors:
        raise SystemExit("browser console errors detected")
    if values.get("title") != "CHA 态势总览 · M2":
        raise SystemExit("unexpected dashboard title")
    if values.get("geoRows", 0) < 1 or values.get("freshnessRows", 0) < 1:
        raise SystemExit("dashboard tables did not render")
    if theme_toggle != "light":
        raise SystemExit("theme switch did not work")


if __name__ == "__main__":
    main()
