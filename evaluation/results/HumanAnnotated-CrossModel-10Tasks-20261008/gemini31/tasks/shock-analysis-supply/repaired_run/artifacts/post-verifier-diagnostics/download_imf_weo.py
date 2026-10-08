from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # We need Georgia real GDP and real GDP growth rate 2000-2027 from October 2023 WEO
        # Navigate to imf datamapper download page
        page.goto('https://www.imf.org/en/Publications/WEO/weo-database/2023/October/weo-report?c=915,&s=NGDP_R,NGDP_RPCH,&sy=2000&ey=2028&ssm=0&scsm=1&scc=0&ssd=1&ssc=0&sic=0&sort=country&ds=.&br=1')
        
        page.screenshot(path="weo_data_page.png")
        print("Saved screenshot of WEO page.")
        
        # Just grab the data from the HTML table
        table_html = page.locator("table").inner_html()
        with open("weo_table.html", "w") as f:
            f.write("<table>" + table_html + "</table>")
            
        print("Saved WEO table HTML.")
                
        browser.close()

run()
