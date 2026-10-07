from playwright.sync_api import sync_playwright
import pandas as pd
import time

def scrape_imf():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        # Go to IMF WEO database (e.g. October 2023)
        page.goto("https://www.imf.org/en/Publications/WEO/weo-database/2023/October/weo-report?c=915,&s=NGDP_R,NGDP_RPCH,&sy=2000&ey=2028&ssm=0&scsm=1&scc=0&sac=1&sort=country&ds=.&br=1")
        
        # Wait for table to load
        page.wait_for_selector("table")
        
        # Get HTML and parse with pandas
        html = page.content()
        
        try:
            # Requires lxml or html5lib to be installed
            dfs = pd.read_html(html)
            if len(dfs) > 0:
                df = dfs[0]
                df.to_csv("weo_data_raw.csv", index=False)
                print("Successfully scraped IMF data")
        except Exception as e:
            print("Error parsing HTML:", e)
        
        browser.close()

if __name__ == "__main__":
    scrape_imf()
