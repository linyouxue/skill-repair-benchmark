from playwright.sync_api import sync_playwright
import time
import pandas as pd
from io import StringIO

def get_ecb_georgia():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        # Go to ECB page for Georgia
        page.goto("https://data.ecb.europa.eu/data/geographical-areas/georgia?reference_area_name%5B0%5D=Georgia")
        
        # We need consumption of fixed capital. Wait for the tables to load.
        page.wait_for_selector(".table-responsive", timeout=20000)
        
        # Wait a bit more for JavaScript to finish loading
        time.sleep(3)
        html = page.content()
        dfs = pd.read_html(StringIO(html))
        
        found = False
        for i, df in enumerate(dfs):
            print(f"Table {i}:", df.columns)
            if any('Consumption of fixed capital' in str(c) for c in df.columns) or any('Consumption of fixed capital' in str(v) for v in df.values):
                print(df.head())
                df.to_csv(f"ecb_table_{i}.csv", index=False)
                found = True
        
        if not found:
            print("Did not find consumption of fixed capital in the tables directly")
            
        browser.close()

if __name__ == "__main__":
    get_ecb_georgia()
