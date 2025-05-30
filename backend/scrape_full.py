#!/usr/bin/env python3
"""
Full-site crawler for madewithnestle.ca.

- Recursively visits every internal page starting from BASE_URL.
- Saves:
    * raw HTML          -> scraped_data_async/<path>.html
    * cleaned text      -> scraped_data_async/<path>_text.json
    * extracted tables  -> scraped_data_async/<path>_tables.json
    * images (binary)   -> scraped_data_async/images/<hash>.<ext>
- Records every visited URL to scraped_data_async/visited_urls.txt
  (one per line, path-only duplicates removed)

Concurrent scraper using Playwright with MAX_CONCURRENCY pages.
"""

import asyncio
import hashlib
import json
import os
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright


# Configuration
BASE_URL = "https://www.madewithnestle.ca"
OUTPUT_DIR = "scraped_data_async"
VISITED_FILE = os.path.join(OUTPUT_DIR, "visited_urls.txt")
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/114.0.0.0 Safari/537.36"
)
VALID_IMG_EXT = (".jpg", ".jpeg", ".png", ".svg", ".gif", ".webp")
MAX_CONCURRENCY = 6

# Bootstrap folders
os.makedirs(os.path.join(OUTPUT_DIR, "images"), exist_ok=True)
# Start fresh visited file
open(VISITED_FILE, "w", encoding="utf-8").close()


def normalize(url: str) -> str:
    """Strip query and fragment, return normalized URL."""
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def is_internal(url: str) -> bool:
    """Check if the URL is internal to BASE_URL."""
    return urlparse(url).netloc == urlparse(BASE_URL).netloc


async def save_image(src: str, session: requests.Session) -> None:
    """Download image if extension is valid, name by MD5 hash."""
    ext = os.path.splitext(urlparse(src).path)[1].lower()
    if ext not in VALID_IMG_EXT:
        return

    try:
        response = session.get(src, timeout=15)
        response.raise_for_status()
        hash_name = hashlib.md5(src.encode()).hexdigest()
        image_path = os.path.join(OUTPUT_DIR, "images", f"{hash_name}{ext}")
        with open(image_path, "wb") as file:
            file.write(response.content)
    except Exception:
        pass


async def process_page(
    url: str,
    page,
    to_crawl: set[str],
    visited: set[str],
    visited_lock: asyncio.Lock,
    session: requests.Session,
) -> None:
    """Scrape one URL, save content, and enqueue new links."""
    if not is_internal(url) or url in visited:
        return

    # Skip recipe filters and search pages
    if "recipe_tags_filter" in url or "/search?" in url:
        return

    print(f"[→] {url}")
    try:
        await page.goto(url, wait_until="networkidle", timeout=120_000)
    except Exception as error:
        print(f"[!] Failed to load {url}: {error}")
        return

    # Accept cookies
    consent_selectors = [
        "button#consent-accept",
        "button.cookie-btn",
        "button:has-text('Accept All')",
    ]
    for selector in consent_selectors:
        try:
            button = await page.query_selector(selector)
            if button:
                await button.click()
                break
        except Exception:
            continue

    # Expand dynamic content
    expand_selectors = [
        "button.dropdown-toggle",
        "button[data-action='expand']",
        "button.accordion-toggle",
    ]
    for selector in expand_selectors:
        elements = await page.query_selector_all(selector)
        for element in elements:
            try:
                await element.click()
            except Exception:
                continue

    # Load more recipes
    if "/recipes" in url:
        while True:
            load_more = await page.query_selector(
                "button.load-more, button[data-action='load-more']"
            )
            if not load_more:
                break
            print("    ↳ Loading more content...")
            await load_more.click()
            await page.wait_for_timeout(2_000)

    # Extract page content
    html_content = await page.content()
    soup = BeautifulSoup(html_content, "html.parser")

    # Derive safe file names
    path_stub = urlparse(url).path.strip("/") or "index"
    safe_name = path_stub.replace("/", "_")

    # Save raw HTML
    html_path = os.path.join(OUTPUT_DIR, f"{safe_name}.html")
    with open(html_path, "w", encoding="utf-8") as file:
        file.write(html_content)

    # Save cleaned text
    texts = [
        element.get_text(strip=True)
        for element in soup.find_all(["p", "h1", "h2", "h3", "li", "span"])
        if element.get_text(strip=True)
    ]
    text_path = os.path.join(OUTPUT_DIR, f"{safe_name}_text.json")
    with open(text_path, "w", encoding="utf-8") as file:
        json.dump(texts, file, ensure_ascii=False, indent=2)

    # Save tables
    tables = []
    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        rows = [
            [td.get_text(strip=True) for td in tr.find_all("td")]
            for tr in table.find_all("tr")
            if tr.find_all("td")
        ]
        if rows:
            tables.append({"headers": headers, "rows": rows})
    tables_path = os.path.join(OUTPUT_DIR, f"{safe_name}_tables.json")
    with open(tables_path, "w", encoding="utf-8") as file:
        json.dump(tables, file, ensure_ascii=False, indent=2)

    # Download images
    image_sources = [
        urljoin(BASE_URL, img["src"])
        for img in soup.find_all("img", src=True)
    ]
    image_tasks = [save_image(src, session) for src in image_sources]
    await asyncio.gather(*image_tasks)

    # Enqueue new links
    hrefs = await page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
    for link in hrefs:
        normalized = normalize(link)
        if is_internal(normalized) and normalized not in visited:
            to_crawl.add(normalized)

    # Record visited URL
    async with visited_lock:
        visited.add(url)
        with open(VISITED_FILE, "a", encoding="utf-8") as file:
            file.write(f"{url}\n")
    print(f"[✓] {url}")


async def crawl() -> None:
    """Main crawler logic: spawn workers and crawl pages."""
    visited: set[str] = set()
    to_crawl: set[str] = {BASE_URL}
    visited_lock = asyncio.Lock()
    session = requests.Session()

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

        async def worker() -> None:
            async with browser.new_context(user_agent=USER_AGENT) as context:
                page = await context.new_page()
                while to_crawl:
                    try:
                        url = to_crawl.pop()
                    except KeyError:
                        break
                    async with semaphore:
                        await process_page(
                            url, page, to_crawl, visited, visited_lock, session
                        )

        tasks = [asyncio.create_task(worker()) for _ in range(MAX_CONCURRENCY)]
        await asyncio.gather(*tasks)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(crawl())