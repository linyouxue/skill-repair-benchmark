import pandas as pd
import requests

url = "https://www.imf.org/-/media/Files/Publications/WEO/WEO-Database/2023/October/WEOOct2023all.xls"
print("Downloading WEO database...")
response = requests.get(url)
with open("weo.tsv", "wb") as f:
    f.write(response.content)
print("Downloaded. Parsing...")

try:
    weo_df = pd.read_csv("weo.tsv", sep='\t', encoding='utf-16', engine='python', on_bad_lines='skip')
    print(weo_df.head(2))
    
    geo_data = weo_df[(weo_df['WEO Country Code'] == '915') | (weo_df['WEO Country Code'] == 915) | (weo_df['Country'] == 'Georgia')]
    
    geo_rgdp = geo_data[geo_data['WEO Subject Code'].isin(['NGDP_R', 'NGDP_RPCH'])]
    print("Found Georgia Data:", len(geo_rgdp))
    
    geo_rgdp.to_csv("geo_weo.csv", index=False)
except Exception as e:
    print("Error parsing:", e)

