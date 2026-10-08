from playwright.sync_api import sync_playwright
import pandas as pd

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        
        # Load the WEO datamapper directly
        page.goto("https://www.imf.org/external/datamapper/NGDP_R/GEO")
        page.wait_for_timeout(5000)
        
        # Now we might be able to extract the chart data from window.imf data objects
        # But this could be complex. Let's just go back to downloading the file or parsing the WEO page
        
        browser.close()

if __name__ == "__main__":
    run()
