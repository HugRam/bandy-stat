"""Scrape stats.innebandy.se roster and schedule using Playwright.

This uses a real browser so JS-rendered content and cookie dialogs work.

Usage (after installing Playwright):
    python scrape_playwright.py

Install Playwright (once) in your venv:
    python -m pip install playwright
    python -m playwright install

Notes:
- The script attempts to click a cookie "accept" button if present ("Acceptera alla" or common ids).
- It extracts anchors whose href contains '/spelare/' to find player names and ids.
- Save to CSV in the current folder.
"""
from playwright.sync_api import sync_playwright
import pandas as pd
import time

TEAM_TRUPP = "https://stats.innebandy.se/sasong/43/lag/24067/trupp"
TEAM_SPELPROGRAM = "https://stats.innebandy.se/sasong/43/lag/24067/spelprogram"


def accept_cookies(page):
    # Try a few common accept selectors / texts; ignore failures
    try_selectors = [
        "button:has-text('Acceptera alla')",
        "button:has-text('Acceptera')",
        "#onetrust-accept-btn-handler",
        "button.cookie-accept",
    ]
    for sel in try_selectors:
        try:
            el = page.query_selector(sel)
            if el:
                el.click()
                # small wait for dialog to disappear
                time.sleep(0.3)
                return True
        except Exception:
            pass
    return False


def scrape_roster(url: str) -> pd.DataFrame:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        accept_cookies(page)
        # wait for potential dynamic content
        page.wait_for_timeout(800)

        # Find the main roster table and extract all columns
        table = page.query_selector("table")
        rows = []
        if table:
            # Get headers and clean them for user-friendly names
            headers = []
            thead = table.query_selector("thead")
            if thead:
                headers = [th.inner_text().strip() for th in thead.query_selector_all("th")]
            # Clean up header names (remove suffixes/prefixes)
            import re
            def clean_header(h):
                h = h.lower()
                h = re.sub(r"(expand_less|unfold_more)", "", h)
                h = h.strip()
                return h
            clean_headers = [clean_header(h) for h in headers]
            idx_map = {h: i for i, h in enumerate(clean_headers)}
            for tr in table.query_selector_all("tbody tr"):
                tds = tr.query_selector_all("td")
                if not tds or len(tds) < 2:
                    continue
                cols = [td.inner_text().strip() for td in tds]
                row = {}
                for h, i in idx_map.items():
                    row[h] = cols[i]
                # Set player_id to number for easier use
                row["player_id"] = row.get("nr", cols[0])
                row["name"] = row.get("namn", cols[1])
                row["position"] = row.get("position", None)
                # Find player link for href
                a = tds[idx_map.get("namn", 1)].query_selector("a") if "namn" in idx_map else None
                row["href"] = a.get_attribute("href") if a else None
                rows.append(row)
        browser.close()
        return pd.DataFrame(rows)


def scrape_generic_links(url: str, href_contains: str) -> pd.DataFrame:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        accept_cookies(page)
        page.wait_for_timeout(800)
        anchors = page.query_selector_all(f"a[href*='{href_contains}']")
        rows = []
        seen = set()
        for a in anchors:
            try:
                href = a.get_attribute("href") or ""
                txt = a.inner_text().strip()
                if not txt:
                    continue
                key = (href, txt)
                if key in seen:
                    continue
                seen.add(key)
                rows.append({"text": txt, "href": href})
            except Exception:
                continue
        browser.close()
        return pd.DataFrame(rows)


if __name__ == "__main__":
    print("Scraping roster with Playwright (may take a few seconds)...")
    try:
        df = scrape_roster(TEAM_TRUPP)
        if not df.empty:
            print(df.head(20))
            df.to_csv("trupp_playwright.csv", index=False)
            print("Saved trupp_playwright.csv")
        else:
            print("No player anchors found on roster page. You can open the page in a browser and inspect anchors.")
    except Exception as e:
        print("Error scraping roster:", e)

    print("\nScraping schedule anchors (generic links)...")
    try:
        df2 = scrape_generic_links(TEAM_SPELPROGRAM, 'match')
        if not df2.empty:
            print(df2.head(20))
            df2.to_csv("spelprogram_playwright.csv", index=False)
            print("Saved spelprogram_playwright.csv")
        else:
            print("No match anchors found on schedule page.")
    except Exception as e:
        print("Error scraping schedule:", e)
