from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto('https://www.imf.org/external/datamapper/api/v1/NGDP_R/GEO?periods=2000')
    print(page.locator('body').inner_text())
    browser.close()
