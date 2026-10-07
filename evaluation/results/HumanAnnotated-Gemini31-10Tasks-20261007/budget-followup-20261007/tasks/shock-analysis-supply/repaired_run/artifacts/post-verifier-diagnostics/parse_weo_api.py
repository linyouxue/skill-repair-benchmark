from playwright.sync_api import sync_playwright
import json
import pandas as pd

def fetch_data():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # NGDP_R
        page.goto("https://www.imf.org/external/datamapper/api/v1/NGDP_R/GEO?periods=2000,2001,2002,2003,2004,2005,2006,2007,2008,2009,2010,2011,2012,2013,2014,2015,2016,2017,2018,2019,2020,2021,2022,2023,2024,2025,2026,2027")
        c1 = page.locator("body").inner_text()
        d1 = json.loads(c1)
        r_data = d1['values']['NGDP_R']['GEO']
        
        # NGDP_RPCH
        page.goto("https://www.imf.org/external/datamapper/api/v1/NGDP_RPCH/GEO?periods=2000,2001,2002,2003,2004,2005,2006,2007,2008,2009,2010,2011,2012,2013,2014,2015,2016,2017,2018,2019,2020,2021,2022,2023,2024,2025,2026,2027")
        c2 = page.locator("body").inner_text()
        d2 = json.loads(c2)
        rpch_data = d2['values']['NGDP_RPCH']['GEO']
        
        browser.close()
        
        df = pd.DataFrame({
            'year': list(r_data.keys()),
            'NGDP_R': list(r_data.values())
        })
        df2 = pd.DataFrame({
            'year': list(rpch_data.keys()),
            'NGDP_RPCH': list(rpch_data.values())
        })

        merged = pd.merge(df, df2, on='year', how='outer')
        merged['year'] = pd.to_numeric(merged['year'])
        merged = merged.sort_values('year')
        merged.to_csv('geo_weo.csv', index=False)
        print("Saved geo_weo.csv")
        print(merged.head())

if __name__ == "__main__":
    fetch_data()
