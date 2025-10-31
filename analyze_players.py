"""Fetch player history pages and create stacked division charts.

Usage:
    python analyze_players.py

Requires Playwright installed and browsers installed:
    python -m pip install -r requirements.txt
    python -m playwright install

Outputs:
- appearances.csv  (player_id, name, competition, raw_cols)
- players_division_stack.png  (stacked bar chart of counts per competition)
"""
import os
import re
import time
import argparse
import pandas as pd
import matplotlib.pyplot as plt
from playwright.sync_api import sync_playwright
try:
    from scrape_playwright import scrape_roster
except Exception:
    scrape_roster = None

# try to read trupp_playwright.csv (preferred) else trupp.csv
TRUPP_PLAYWRIGHT = "trupp_playwright.csv"
TRUPP_CSV = "trupp.csv"

# simple cookie accept helper (same heuristics as scrape_playwright)
def _accept_cookies(page):
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
                page.wait_for_timeout(250)
                return True
        except Exception:
            pass
    return False


def fetch_player_appearances(href: str, max_wait_ms: int = 2000):
    """Return a list of appearance dicts for a player page URL.

    Each dict contains at least 'competition' and 'raw_cols'.
    """
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(href, wait_until="networkidle")
        _accept_cookies(page)
        page.wait_for_timeout(500)

        # Find the <h4> with text '2025/26' and get the next <table> sibling
        season_table = None
        h4s = page.query_selector_all("h4")
        for h4 in h4s:
            if "2025/26" in h4.inner_text():
                # Try to get the next sibling table
                table = h4.evaluate_handle("el => el.nextElementSibling")
                if table and table.evaluate("el => el.tagName.toLowerCase()") == "table":
                    season_table = table
                    break

        # Fallback: use first table if not found
        if not season_table:
            tables = page.query_selector_all("table")
            season_table = tables[0] if tables else None

        if season_table:
            headers = []
            thead = season_table.query_selector("thead")
            if thead:
                headers = [th.inner_text().strip() for th in thead.query_selector_all("th")]
            col_map = {h.lower(): i for i, h in enumerate(headers)}
            for tr in season_table.query_selector_all("tbody tr"):
                tds = tr.query_selector_all("td")
                if not tds or len(tds) < len(headers):
                    continue
                # Extract all columns, including TOTALT row
                row_data = {
                    "competition": tds[col_map.get("tävling", 0)].inner_text().strip() if "tävling" in col_map else "",
                    "team": tds[col_map.get("lag", 1)].inner_text().strip() if "lag" in col_map else "",
                    "matches": tds[col_map.get("ma", 2)].inner_text().strip() if "ma" in col_map else "",
                    "goals": tds[col_map.get("må", 3)].inner_text().strip() if "må" in col_map else "",
                    "assists": tds[col_map.get("ass", 4)].inner_text().strip() if "ass" in col_map else "",
                    "points": tds[col_map.get("p", 5)].inner_text().strip() if "p" in col_map else "",
                    "penalty": tds[col_map.get("utv", 6)].inner_text().strip() if "utv" in col_map else ""
                }
                rows.append(row_data)
        browser.close()
    return rows


def _looks_like_division(text: str) -> bool:
    if not text:
        return False
    text = text.lower()
    # basic heuristics: contains known Swedish words or common labels
    tokens = ["herr", "junior", "p09", "p-09", "p10", "flick", "allsvenskan", "division", "serie", "jun", "9-manna", "7-manna"]
    for t in tokens:
        if t in text:
            return True
    # also accept short codes like 'JAS', 'P09'
    if re.match(r"^[A-ZÅÄÖ0-9\- ]{1,12}$", text) and any(ch.isdigit() for ch in text):
        return True
    return False


def main():
    # Always use trupp.csv (latest)
    if os.path.exists(TRUPP_CSV):
        trupp = pd.read_csv(TRUPP_CSV)
    else:
        print("No roster CSV found. Run main.py first.")
        return

    print("Columns detected in trupp.csv:", list(trupp.columns))
    print("Sample data:")
    print(trupp.head(10).to_string(index=False))

    # For each player, fetch their profile and extract appearance stats
    appearances = []
    BASE_URL = "https://stats.innebandy.se"
    for idx, row in trupp.iterrows():
        name = row.get("namn") or row.get("name")
        position = row.get("position", "?")
        href = row.get("href")
        if not isinstance(href, str) or not href.strip():
            continue
        # Ensure href is absolute
        if href.startswith("/"):
            href_full = BASE_URL + href
        elif href.startswith("http"):
            href_full = href
        else:
            href_full = BASE_URL + "/" + href
        # Prefix position: F, B, M
        pos_prefix = "F" if "forw" in position.lower() else ("B" if "back" in position.lower() else ("M" if "mål" in position.lower() else "?"))
        player_label = f"{pos_prefix}-{name}"
        print(f"Fetching appearances for {player_label} ...")
        try:
            player_rows = fetch_player_appearances(href_full)
            for pr in player_rows:
                comp = pr.get("competition")
                team = pr.get("team")
                matches = pr.get("matches")
                goals = pr.get("goals")
                assists = pr.get("assists")
                points = pr.get("points")
                penalty = pr.get("penalty")
                # Only count real leagues/divisions (ignore empty, numeric-only)
                if not comp or comp.strip() == "" or comp.strip().isdigit():
                    continue
                appearances.append({
                    "player": player_label,
                    "division": comp.strip(),
                    "team": team,
                    "matches": matches,
                    "goals": goals,
                    "assists": assists,
                    "points": points,
                    "penalty": penalty
                })
            time.sleep(0.2)
        except Exception as e:
            print(f"Failed to fetch {player_label}: {e}")

    if not appearances:
        print("No appearance rows found for any player.")
        return

    df_app = pd.DataFrame(appearances)
    df_app.to_csv("appearances.csv", index=False)
    print("Saved all player appearances to appearances.csv")

    # Reload from appearances.csv and clean up
    df_app = pd.read_csv("appearances.csv")
    # Convert matches to integer, invalid values become 0
    def safe_int(x):
        try:
            return int(x)
        except Exception:
            return 0
    df_app["matches"] = df_app["matches"].apply(safe_int)

    # Separate TOTALT rows for validation
    is_total = df_app["division"].str.upper() == "TOTALT"
    df_total = df_app[is_total]
    df_app = df_app[~is_total]
    # Clean up missing/empty divisions and only keep rows with matches > 0
    df_app = df_app[df_app["division"].notna() & (df_app["division"] != "") & (df_app["matches"] > 0)]

    # Pivot: index=player, columns=division, values=matches
    pivot = df_app.pivot_table(index="player", columns="division", values="matches", aggfunc="sum", fill_value=0)
    if pivot.empty:
        print("No division appearance data to plot.")
        return

    # Show all players, but limit divisions for readability (max 8 divisions)
    if len(pivot.columns) > 8:
        keep_divs = list(pivot.sum().sort_values(ascending=False).index[:8])
        pivot = pivot[keep_divs]

    ax = pivot.plot(kind="bar", stacked=True, figsize=(max(12, len(pivot)), 7), colormap="tab20")
    ax.set_title("Player appearances by division/series (stacked)")
    ax.set_ylabel("Matches played")
    plt.xticks(rotation=45, ha="right")
    yticks = list(range(0, max(25, int(pivot.values.max())+5), 5))
    ax.set_yticks(yticks)
    ax.grid(axis='y', which='major', linestyle='-', linewidth=0.5, color='gray', zorder=0)
    ax.set_ylim(0, yticks[-1])
    plt.tight_layout()
    # Add legend below chart for division names
    ax.legend(title="Division/Series", bbox_to_anchor=(0.5, -0.18), loc="upper center", ncol=2)
    out = "players_division_stack.png"
    plt.savefig(out, bbox_inches="tight")
    print(f"Saved stacked chart to {out}")

    # Validation: print any mismatches between sum of matches and TOTALT
    for player in pivot.index:
        total_row = df_total[df_total["player"] == player]
        if not total_row.empty:
            total_matches = total_row.iloc[0]["matches"]
            sum_matches = pivot.loc[player].sum()
            if total_matches != sum_matches:
                print(f"WARNING: {player} sum of matches ({sum_matches}) does not match TOTALT ({total_matches})")

    # --- New plot: players-per-league stacked chart ---
    # Create a binary matrix: for each division (league) and player, 1 if player played >=1 match
    bin_df = df_app.copy()
    bin_df['played_flag'] = bin_df['matches'].apply(lambda x: 1 if int(x) > 0 else 0)
    # Pivot: index = division, columns = player, value = played_flag (use max to collapse duplicates)
    players_per_league = bin_df.pivot_table(index='division', columns='player', values='played_flag', aggfunc='max', fill_value=0)
    if players_per_league.empty:
        print("No data for players-per-league plot.")
        return

    # Optionally limit leagues for readability (keep top 12 by number of players)
    league_counts = players_per_league.sum(axis=1).sort_values(ascending=False)
    keep_leagues = list(league_counts.index[:12])
    players_per_league = players_per_league.loc[keep_leagues]

    # Plot stacked bars: each column is a player, stacked per league
    ax2 = players_per_league.plot(kind='bar', stacked=True, figsize=(12, max(6, len(players_per_league)/2)), colormap='tab20')
    ax2.set_title('Number of distinct players per league (each player counts 1)')
    ax2.set_ylabel('Number of players')
    # Keep division names visible, but remove the long player legend below to reduce clutter
    # (division names are on the x-axis index)
    # y-grid at 1,2,3... up to max
    max_players = int(players_per_league.sum(axis=1).max())
    ax2.set_yticks(range(0, max(5, max_players+1)))
    ax2.grid(axis='y', which='major', linestyle='-', linewidth=0.5, color='gray', zorder=0)
    plt.tight_layout()
    # Remove the player legend to avoid a huge list of names under the chart
    leg = ax2.get_legend()
    if leg:
        leg.remove()
    out2 = 'players_per_league_stack.png'
    plt.savefig(out2, bbox_inches='tight')
    print(f"Saved players-per-league stacked chart to {out2}")


def analyze_trupp(trupp: pd.DataFrame, out_prefix: str = "", max_divisions: int = 8, max_leagues: int = 12):
    """Run the full analysis on a trupp DataFrame and save outputs with optional prefix.

    Returns the appearances DataFrame (cleaned).
    """
    print("Columns detected in trupp.csv:", list(trupp.columns))
    print("Sample data:")
    print(trupp.head(10).to_string(index=False))

    # For each player, fetch their profile and extract appearance stats
    appearances = []
    BASE_URL = "https://stats.innebandy.se"
    for idx, row in trupp.iterrows():
        name = row.get("namn") or row.get("name")
        position = row.get("position", "?")
        href = row.get("href")
        if not isinstance(href, str) or not href.strip():
            continue
        # Ensure href is absolute
        if href.startswith("/"):
            href_full = BASE_URL + href
        elif href.startswith("http"):
            href_full = href
        else:
            href_full = BASE_URL + "/" + href
        # Prefix position: F, B, M
        pos_prefix = "F" if "forw" in position.lower() else ("B" if "back" in position.lower() else ("M" if "mål" in position.lower() else "?"))
        player_label = f"{pos_prefix}-{name}"
        print(f"Fetching appearances for {player_label} ...")
        try:
            player_rows = fetch_player_appearances(href_full)
            for pr in player_rows:
                comp = pr.get("competition")
                team = pr.get("team")
                matches = pr.get("matches")
                goals = pr.get("goals")
                assists = pr.get("assists")
                points = pr.get("points")
                penalty = pr.get("penalty")
                # Only count real leagues/divisions (ignore empty, numeric-only)
                if not comp or comp.strip() == "" or comp.strip().isdigit():
                    continue
                appearances.append({
                    "player": player_label,
                    "division": comp.strip(),
                    "team": team,
                    "matches": matches,
                    "goals": goals,
                    "assists": assists,
                    "points": points,
                    "penalty": penalty
                })
            time.sleep(0.2)
        except Exception as e:
            print(f"Failed to fetch {player_label}: {e}")

    if not appearances:
        print("No appearance rows found for any player.")
        return pd.DataFrame()

    df_app = pd.DataFrame(appearances)
    app_csv = f"{out_prefix}appearances.csv" if out_prefix else "appearances.csv"
    df_app.to_csv(app_csv, index=False)
    print(f"Saved all player appearances to {app_csv}")

    # Reload from appearances.csv and clean up
    df_app = pd.read_csv(app_csv)
    # Convert matches to integer, invalid values become 0
    def safe_int(x):
        try:
            return int(x)
        except Exception:
            return 0
    df_app["matches"] = df_app["matches"].apply(safe_int)

    # Separate TOTALT rows for validation
    is_total = df_app["division"].str.upper() == "TOTALT"
    df_total = df_app[is_total]
    df_app = df_app[~is_total]
    # Clean up missing/empty divisions and only keep rows with matches > 0
    df_app = df_app[df_app["division"].notna() & (df_app["division"] != "") & (df_app["matches"] > 0)]

    # Pivot: index=player, columns=division, values=matches
    pivot = df_app.pivot_table(index="player", columns="division", values="matches", aggfunc="sum", fill_value=0)
    if pivot.empty:
        print("No division appearance data to plot.")
        return df_app

    # Show all divisions; make the figure wider if there are many divisions so labels remain readable
    pivot_plot = pivot.copy()
    # dynamic width: ~0.6 inch per division, min 12 inches
    width = max(12, int(len(pivot_plot.columns) * 0.6))
    ax = pivot_plot.plot(kind="bar", stacked=True, figsize=(width, 7), colormap="tab20")
    ax.set_title("Player appearances by division/series (stacked)")
    ax.set_ylabel("Matches played")
    plt.xticks(rotation=45, ha="right")
    yticks = list(range(0, max(25, int(pivot_plot.values.max())+5), 5))
    ax.set_yticks(yticks)
    ax.grid(axis='y', which='major', linestyle='-', linewidth=0.5, color='gray', zorder=0)
    ax.set_ylim(0, yticks[-1])
    plt.tight_layout()
    # Add legend below chart for division names
    ax.legend(title="Division/Series", bbox_to_anchor=(0.5, -0.18), loc="upper center", ncol=2)
    out = f"{out_prefix}players_division_stack.png" if out_prefix else "players_division_stack.png"
    plt.savefig(out, bbox_inches="tight")
    print(f"Saved stacked chart to {out}")

    # Validation: print any mismatches between sum of matches and TOTALT
    for player in pivot.index:
        total_row = df_total[df_total["player"] == player]
        if not total_row.empty:
            total_matches = total_row.iloc[0]["matches"]
            sum_matches = pivot.loc[player].sum()
            if total_matches != sum_matches:
                print(f"WARNING: {player} sum of matches ({sum_matches}) does not match TOTALT ({total_matches})")

    # --- New plot: players-per-league stacked chart ---
    # Create a binary matrix: for each division (league) and player, 1 if player played >=1 match
    bin_df = df_app.copy()
    bin_df['played_flag'] = bin_df['matches'].apply(lambda x: 1 if int(x) > 0 else 0)
    # Pivot: index = division, columns = player, value = played_flag (use max to collapse duplicates)
    players_per_league = bin_df.pivot_table(index='division', columns='player', values='played_flag', aggfunc='max', fill_value=0)
    if players_per_league.empty:
        print("No data for players-per-league plot.")
        return df_app

    # Keep all leagues and make figure wider if needed so division names stay readable
    width2 = max(12, int(len(players_per_league.index) * 0.6))
    # Plot stacked bars: each column is a player, stacked per league
    ax2 = players_per_league.plot(kind='bar', stacked=True, figsize=(width2, max(6, len(players_per_league)/2)), colormap='tab20')
    ax2.set_title('Number of distinct players per league (each player counts 1)')
    ax2.set_ylabel('Number of players')
    # Tilt division names for readability and remove the long player legend below to reduce clutter
    plt.xticks(rotation=45, ha='right')
    leg = ax2.get_legend()
    if leg:
        leg.remove()
    # y-grid at 1,2,3... up to max
    max_players = int(players_per_league.sum(axis=1).max())
    ax2.set_yticks(range(0, max(5, max_players+1)))
    ax2.grid(axis='y', which='major', linestyle='-', linewidth=0.5, color='gray', zorder=0)
    plt.tight_layout()
    out2 = f'{out_prefix}players_per_league_stack.png' if out_prefix else 'players_per_league_stack.png'
    plt.savefig(out2, bbox_inches='tight')
    print(f"Saved players-per-league stacked chart to {out2}")

    return df_app


def main():
    parser = argparse.ArgumentParser(description='Analyze players appearances (single team or from URL)')
    parser.add_argument('--trupp', type=str, default=TRUPP_CSV, help='Path to trupp CSV')
    parser.add_argument('--team-url', type=str, help='Team roster URL to scrape instead of using a CSV')
    parser.add_argument('--out-prefix', type=str, default='', help='Prefix for output files (e.g., team name_)')
    parser.add_argument('--player', type=str, help='If set, only analyze players whose name contains this substring (case-insensitive)')
    parser.add_argument('--max-divisions', type=int, default=8, help='Max divisions to display on per-player chart; others aggregated into Other (0 = keep all)')
    parser.add_argument('--max-leagues', type=int, default=12, help='Max leagues to display on players-per-league chart; others aggregated into Other (0 = keep all)')
    args = parser.parse_args()

    if args.team_url:
        if scrape_roster is None:
            print('scrape_playwright.py not available; cannot scrape team URL')
            return
        print(f'Scraping roster from {args.team_url} ...')
        trupp = scrape_roster(args.team_url)
        if trupp.empty:
            print('Failed to scrape roster from URL')
            return
    else:
        if not os.path.exists(args.trupp):
            print(f'Roster CSV not found: {args.trupp}')
            return
        trupp = pd.read_csv(args.trupp)

    # optional player filter
    if args.player:
        mask = trupp.apply(lambda r: args.player.lower() in (str(r.get('namn') or r.get('name') or '')).lower(), axis=1)
        trupp = trupp[mask]
        if trupp.empty:
            print(f'No players matching "{args.player}" found in roster')
            return

    analyze_trupp(trupp, out_prefix=args.out_prefix, max_divisions=args.max_divisions, max_leagues=args.max_leagues)


if __name__ == "__main__":
    main()
