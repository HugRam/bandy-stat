import os
import pandas as pd
from processing import clean_trupp, save_csv

# try to use Playwright-based scraper if available (handles JS + cookies)
try:
    from scrape_playwright import scrape_roster, scrape_generic_links
    HAVE_PLAYWRIGHT = True
except Exception:
    HAVE_PLAYWRIGHT = False

from data_fetch import scrape_trupp, scrape_spelprogram

TEAM_TRUPP = "https://stats.innebandy.se/sasong/43/lag/24067/trupp"
TEAM_SPELPROGRAM = "https://stats.innebandy.se/sasong/43/lag/24067/spelprogram"


def main():
    print("Starting fetch...")

    trupp = None
    # Only use Playwright scraper for roster (requests fallback removed)
    if HAVE_PLAYWRIGHT:
        try:
            print("Using Playwright scraper for roster...")
            trupp = scrape_roster(TEAM_TRUPP)
            if trupp is not None and not trupp.empty:
                trupp = clean_trupp(trupp)
                save_csv(trupp, "trupp.csv")
                print(f"Saved trupp.csv ({len(trupp)} rows) from Playwright")
                try:
                    print("--- trupp (sample) ---")
                    print(trupp.head(20).to_string(index=False))
                except Exception:
                    print(trupp.head(20))
            else:
                print("Playwright scraper returned no players.")
        except Exception as e:
            print("Playwright roster scraper failed:", e)
    else:
        print("Playwright is required for roster scraping. Please install Playwright and browsers.")

    # --- schedule / spelprogram ---
    sched = None
    if HAVE_PLAYWRIGHT:
        try:
            print("Using Playwright scraper for schedule links...")
            sched = scrape_generic_links(TEAM_SPELPROGRAM, 'match')
            if sched is not None and not sched.empty:
                save_csv(sched, "spelprogram.csv")
                print(f"Saved spelprogram.csv ({len(sched)} rows) from Playwright")
                # print a preview of schedule links
                try:
                    print("--- spelprogram (sample) ---")
                    print(sched.head(20).to_string(index=False))
                except Exception:
                    print(sched.head(20))
            else:
                print("Playwright schedule scraper returned no match anchors. See spelprogram_playwright.csv for other links.")
        except Exception as e:
            print("Playwright schedule scraper failed:", e)

    if sched is None or sched.empty:
        try:
            print("Falling back to requests-based scraper for schedule...")
            sched = scrape_spelprogram(TEAM_SPELPROGRAM)
            if sched is not None and not sched.empty:
                save_csv(sched, "spelprogram.csv")
                print(f"Saved spelprogram.csv ({len(sched)} rows) from requests scraper")
            else:
                print("No schedule rows found. Inspect selectors in data_fetch.scrape_spelprogram().")
        except Exception as e:
            print("Failed to fetch schedule:", e)


if __name__ == "__main__":
    main()
