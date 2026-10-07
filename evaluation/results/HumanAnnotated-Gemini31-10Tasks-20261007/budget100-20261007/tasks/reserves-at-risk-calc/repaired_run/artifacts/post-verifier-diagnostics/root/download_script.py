from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.webkit.launch(headless=True)
        page = browser.new_page()
        page.goto("https://www.imf.org/en/research/commodity-prices")
        
        with page.expect_download() as download_info:
            page.click("a[href*='external-data.xlsx']")
        
        download = download_info.value
        download.save_as("imf_external_data.xlsx")
        print("Success")
        browser.close()

if __name__ == "__main__":
    run()
