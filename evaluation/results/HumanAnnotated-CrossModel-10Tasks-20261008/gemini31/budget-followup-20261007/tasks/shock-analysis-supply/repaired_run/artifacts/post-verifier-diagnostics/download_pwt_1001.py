import urllib.request
import re
from playwright.sync_api import sync_playwright

def get_pwt():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("https://www.rug.nl/ggdc/productivity/pwt/?lang=en")
        print(page.title())
        print(page.locator("body").inner_text()[:1000])
        browser.close()

if __name__ == "__main__":
    get_pwt()
