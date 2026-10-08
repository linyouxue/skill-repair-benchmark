from playwright.sync_api import sync_playwright
import json

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        # Intercept network requests to bypass blocks if necessary
        page.goto("https://www.imf.org/external/datamapper/api/v1/NGDP_R/GEO")
        content = page.content()
        print("NGDP_R", content[:200])
        
        page.goto("https://www.imf.org/external/datamapper/api/v1/NGDP_RPCH/GEO")
        content = page.content()
        print("NGDP_RPCH", content[:200])
        
        browser.close()

if __name__ == "__main__":
    run()
