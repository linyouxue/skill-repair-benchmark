import json
from playwright.sync_api import sync_playwright
import pandas as pd

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        page.goto("https://www.imf.org/external/datamapper/api/v1/NGDP_R/GEO")
        content = page.locator("body").inner_text()
        print(content[:200])
        
        browser.close()

if __name__ == "__main__":
    run()
