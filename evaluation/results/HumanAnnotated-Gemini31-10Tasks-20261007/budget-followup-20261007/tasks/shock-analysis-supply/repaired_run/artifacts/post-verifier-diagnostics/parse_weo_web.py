from playwright.sync_api import sync_playwright

def fetch_data():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        # the WEO datamapper actually has multiple datasets, maybe we just do this:
        page.goto("https://www.imf.org/external/datamapper/api/v1/NGDP_R/GEO")
        print("NGDP_R", page.locator("body").inner_text())
        
        page.goto("https://www.imf.org/external/datamapper/api/v1/NGDP_RPCH/GEO")
        print("NGDP_RPCH", page.locator("body").inner_text())
        
        browser.close()

if __name__ == "__main__":
    fetch_data()
