from playwright.sync_api import sync_playwright

def get_pwt11():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("https://www.rug.nl/ggdc/productivity/pwt/?lang=en")
        
        # Let's get the URL of the excel link first to just download it manually if expect_download takes too long
        link = page.locator("a:has-text('Excel')").first.get_attribute('href')
        print(link)
        browser.close()

if __name__ == "__main__":
    get_pwt11()
