import urllib.request
import os
import pandas as pd

url = "https://www.imf.org/-/media/Files/Publications/WEO/WEO-Database/2023/October/WEOOct2023all.xls"
urllib.request.urlretrieve(url, "weo.tsv")

print(os.path.getsize("weo.tsv"))
with open("weo.tsv", "r", encoding="iso-8859-1") as f:
    print(f.read(100))

