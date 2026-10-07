from playwright.sync_api import sync_playwright

def get_ecb_georgia():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        # Go directly to the dataset page
        page.goto("https://data.ecb.europa.eu/data/datasets/IDCS/IDCS.A.N.GE.W0.S1.S1.N.D.P51C._Z._Z._Z.XDC._Z.S.V.N._T")
        page.wait_for_timeout(5000)
        
        try:
            with page.expect_download() as download_info:
                page.locator("button:has-text('Download')").first.click()
                page.locator("a:has-text('CSV')").first.click()
            download = download_info.value
            download.save_as("ecb_data.csv")
            print("Downloaded ecb_data.csv")
        except Exception as e:
            print("Failed normal download button:", e)
            try:
                # the dataset API URL for CSV is usually:
                url = "https://data-api.ecb.europa.eu/service/data/IDCS/A.N.GE.W0.S1.S1.N.D.P51C._Z._Z._Z.XDC._Z.S.V.N._T?format=csvdata"
                page.goto(url)
                print(page.locator("body").inner_text()[:500])
            except Exception as e2:
                print("Failed direct URL:", e2)
                
        browser.close()

if __name__ == "__main__":
    get_ecb_georgia()
