from playwright.sync_api import sync_playwright
import json
import pandas as pd
import time

def fetch_data():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        
        # Weo Datamapper has real GDP as NGDP_R. 
        page.goto("https://www.imf.org/external/datamapper/api/v1/NGDP_R/GEO")
        time.sleep(1)
        c1 = page.locator("body").inner_text()
        d1 = json.loads(c1)
        if 'values' in d1:
            print("found values in d1")
        else:
            print("no values in d1")
        
        browser.close()

if __name__ == "__main__":
    fetch_data()
