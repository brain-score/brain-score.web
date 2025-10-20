#!/usr/bin/env python3
"""
compare_brain_score_leaderboards_playwright_v2.py

Renders local + archived Brain-Score leaderboards with Playwright,
extracts models + average scores, computes differences, and flags
significant changes (|diff| > 0.01).
"""

import pandas as pd
from datetime import datetime
from playwright.sync_api import sync_playwright

# === CONFIG ===
LOCAL_URL = (
    "http://localhost:8000/vision/leaderboard/"
    "?min_param_count=0&max_param_count=900"
    "&min_model_size=0&max_model_size=4000"
    "&min_score=0&max_score=1"
    "&min_stimuli_count=0&max_stimuli_count=51000"
    "&min_wayback_timestamp=1598486400"
    "&max_wayback_timestamp=1724457600"
)
ARCHIVE_URL = "https://web.archive.org/web/20240824001822/https://www.brain-score.org/vision/"
OUTPUT_FILE = "brain_score_leaderboard_differences.csv"


def scrape_leaderboard(page, label):
    """Extract model names and scores from rendered leaderboard, adapting to unknown column IDs."""
    print(f"🔎 Parsing {label} leaderboard ...")
    page.wait_for_selector("div.ag-center-cols-container div.ag-row", timeout=60000)

    # Inspect first row to find actual column IDs
    first_row = page.query_selector("div.ag-center-cols-container div.ag-row")
    if not first_row:
        print(f"⚠️ No rows found in {label} leaderboard.")
        return pd.DataFrame()

    all_cells = first_row.query_selector_all("div[col-id]")
    col_ids = [c.get_attribute("col-id") for c in all_cells if c.get_attribute("col-id")]
    print(f"🧩 {label} detected column IDs: {col_ids[:10]} ...")

    # Try to infer which col-id represents model and average
    model_col = next((c for c in col_ids if "model" in c.lower()), None)
    avg_col = next((c for c in col_ids if "average" in c.lower() or "vision_v0" in c.lower()), None)

    if not model_col or not avg_col:
        print(f"❌ Could not identify model or average score columns for {label}.")
        return pd.DataFrame()

    rows = page.query_selector_all("div.ag-center-cols-container div.ag-row")
    data = []
    for row in rows:
        model_el = row.query_selector(f"div[col-id='{model_col}']")
        score_el = row.query_selector(f"div[col-id='{avg_col}']")
        if model_el and score_el:
            model = model_el.inner_text().strip()
            score_text = score_el.inner_text().strip()
            try:
                score = float(score_text)
                data.append({"model": model, f"score_{label}": score})
            except ValueError:
                continue

    df = pd.DataFrame(data)
    print(f"✅ Parsed {len(df)} models from {label} leaderboard")
    return df


def main():
    print(f"🧠 Brain-Score Leaderboard Comparison — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # --- Local leaderboard ---
        print(f"🌐 Fetching Local leaderboard: {LOCAL_URL}")
        page.goto(LOCAL_URL, timeout=90000)
        local_df = scrape_leaderboard(page, "local")

        # --- Archive leaderboard ---
        print(f"\n🌐 Fetching Archive leaderboard: {ARCHIVE_URL}")
        page.goto(ARCHIVE_URL, timeout=120000)
        archive_df = scrape_leaderboard(page, "archive")

        browser.close()

    if local_df.empty or archive_df.empty:
        print("\n❌ One of the leaderboards could not be parsed. Check detected column IDs above.")
        return

    # --- Merge & compare ---
    merged = pd.merge(local_df, archive_df, on="model", how="outer")
    merged["diff"] = merged["score_local"] - merged["score_archive"]
    merged["significant_change"] = merged["diff"].abs() > 0.01
    merged["significant_change"] = merged["significant_change"].map({True: "YES", False: "NO"})

    merged.to_csv(OUTPUT_FILE, index=False)
    print(f"\n✅ Comparison complete. Saved to: {OUTPUT_FILE}\n")
    print("📊 Preview:")
    print(merged.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
