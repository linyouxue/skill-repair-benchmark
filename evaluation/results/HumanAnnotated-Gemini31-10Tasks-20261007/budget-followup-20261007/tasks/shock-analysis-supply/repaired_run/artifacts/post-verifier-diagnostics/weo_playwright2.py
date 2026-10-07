from playwright.sync_api import sync_playwright
import json
import pandas as pd
import time

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        page.goto("https://www.imf.org/external/datamapper/api/v1/NGDP_R/GEO")
        content = page.locator("body").inner_text()
        print(content[:300])
        
        browser.close()

if __name__ == "__main__":
    run()
