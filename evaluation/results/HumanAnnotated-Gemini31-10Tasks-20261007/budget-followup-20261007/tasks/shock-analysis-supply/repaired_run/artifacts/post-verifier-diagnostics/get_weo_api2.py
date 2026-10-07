import pandas as pd
import requests

url = "https://www.imf.org/-/media/Files/Publications/WEO/WEO-Database/2024/April/WEOApr2024all.xls"
print("Downloading WEO database...")
response = requests.get(url)
with open("weo.tsv", "wb") as f:
    f.write(response.content)

with open("weo.tsv", "r", encoding="utf-8") as f:
    print(f.read(100))

