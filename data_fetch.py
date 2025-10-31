"""Scrapers for stats.innebandy.se team pages (starter)

This file contains resilient scraping helpers for the team's roster (/trupp)
and schedule (/spelprogram). You'll likely need to adapt selectors after
inspecting the real page HTML.
"""
import re
import time
from typing import List, Dict

import requests
import pandas as pd
from bs4 import BeautifulSoup

# polite headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; StatsScraper/1.0; +https://example.com)"
}

DEFAULT_TIMEOUT = 12


def fetch_soup(url: str, timeout: int = DEFAULT_TIMEOUT) -> BeautifulSoup:
    """Fetch URL and return BeautifulSoup object (lxml parser).
    Raises requests.HTTPError on bad status.
    """
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    # small polite delay (caller can increase)
    time.sleep(0.2)
    return BeautifulSoup(r.text, "lxml")


def _extract_id_from_href(href: str) -> str:
    """Extract first long-ish number from an href, used as a fallback id.
    Returns None if not found.
    """
    if not href:
        return None
    m = re.search(r"/(\d{3,})\b", href)
    return m.group(1) if m else None


def scrape_trupp(url: str) -> pd.DataFrame:
    """Scrape a team roster page (/trupp) and return a DataFrame with
    columns: player_id (optional), name, number (optional), position (optional)

    The function uses a few heuristics to find player rows (tables, links).
    Inspect the real page and adapt selectors if the output is empty.
    """
    # This function is now deprecated. Use Playwright-based scraper for robust roster extraction.
    print("[INFO] scrape_trupp is deprecated. Use Playwright-based scraping via main.py or scrape_playwright.py.")
    return pd.DataFrame([])


def scrape_spelprogram(url: str) -> pd.DataFrame:
    """Scrape the team's schedule (/spelprogram) and return DataFrame with
    columns: match_id (if present), date, opponent, competition, link

    Again, the site structure may require small selector changes.
    """
    soup = fetch_soup(url)
    rows: List[Dict] = []

    # look for a table of matches
    table = soup.find("table")
    if table:
        for tr in table.find_all("tr"):
            tds = tr.find_all(["td", "th"])
            if not tds:
                continue
            texts = [td.get_text(strip=True) for td in tds]
            # Heuristic mapping — adapt if columns differ
            # Common patterns: date | time | opponent | competition | result
            date = None
            opponent = None
            competition = None
            link = None
            for td in tds:
                a = td.find("a")
                if a and a.has_attr("href"):
                    href = a["href"]
                    # match link
                    if "/match/" in href or "/match/" in href:
                        link = href
                        opponent = a.get_text(strip=True)
                    else:
                        # sometimes opponent is link too
                        opponent = opponent or a.get_text(strip=True)
            # fallback to textual heuristics
            if len(texts) >= 3:
                date = texts[0]
                opponent = opponent or texts[2]
                competition = texts[3] if len(texts) > 3 else None
            # extract match id if present
            match_id = _extract_id_from_href(link) if link else None
            rows.append({"match_id": match_id, "date": date, "opponent": opponent, "competition": competition, "link": link, "raw_cols": texts})

    # fallback: look for list items or anchors with "match" keywords
    if not rows:
        for a in soup.find_all("a", href=True):
            txt = a.get_text(strip=True)
            if "match" in txt.lower() or re.search(r"\d{4}-\d{2}-\d{2}", txt):
                match_id = _extract_id_from_href(a["href"])
                rows.append({"match_id": match_id, "date": txt, "opponent": None, "competition": None, "link": a["href"], "raw_cols": [txt]})

    return pd.DataFrame(rows)


if __name__ == "__main__":
    # Example quick run using the URLs you provided. Adjust if you prefer.
    TEAM_TRUPP = "https://stats.innebandy.se/sasong/43/lag/24067/trupp"
    TEAM_SPELPROGRAM = "https://stats.innebandy.se/sasong/43/lag/24067/spelprogram"

    print("Fetching roster (trupp)...")
    try:
        df_trupp = scrape_trupp(TEAM_TRUPP)
        print(df_trupp.head(10))
        df_trupp.to_csv("trupp.csv", index=False)
        print("Saved trupp.csv")
    except Exception as e:
        print("Error fetching roster:", e)

    print("\nFetching schedule (spelprogram)...")
    try:
        df_schedule = scrape_spelprogram(TEAM_SPELPROGRAM)
        print(df_schedule.head(10))
        df_schedule.to_csv("spelprogram.csv", index=False)
        print("Saved spelprogram.csv")
    except Exception as e:
        print("Error fetching schedule:", e)
