#!/usr/bin/env python3
"""
Authenticate via browser and save Cloudflare-passed storage state.

Opens a visible Chromium window for manual human verification on
https://www.madewithnestle.ca, then writes the authenticated
storage state to 'auth.json'.
"""

import asyncio

from playwright.async_api import async_playwright


def save_auth_cookie() -> None:
    """
    Launch a visible browser, navigate to the target site for manual
    Cloudflare challenge resolution, then save the storage state.
    """
    async def run() -> None:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()

            print("Opening Nestlé homepage for verification...")
            await page.goto(
                "https://www.madewithnestle.ca",
                wait_until="domcontentloaded",
                timeout=120_000,
            )

            print("Waiting 30 seconds for manual challenge completion...")
            await page.wait_for_timeout(30_000)

            await context.storage_state(path="auth.json")
            print("Authenticated state saved to auth.json")

            await browser.close()

    asyncio.run(run())


if __name__ == "__main__":
    save_auth_cookie()
