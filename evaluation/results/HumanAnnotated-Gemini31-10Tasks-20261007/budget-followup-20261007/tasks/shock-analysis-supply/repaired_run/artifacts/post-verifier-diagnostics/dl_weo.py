from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("https://www.imf.org/en/Publications/WEO/weo-database/2024/April/weo-report?c=915,&s=NGDP_R,NGDP_RPCH,&sy=2000&ey=2027&ssm=0&scsm=1&scc=0&sac=1&sort=country&ds=.&br=1")
        print("Page title:", page.title())
        html = page.content()
        with open("weo_table.html", "w") as f:
            f.write(html)
        browser.close()

if __name__ == "__main__":
    run()
