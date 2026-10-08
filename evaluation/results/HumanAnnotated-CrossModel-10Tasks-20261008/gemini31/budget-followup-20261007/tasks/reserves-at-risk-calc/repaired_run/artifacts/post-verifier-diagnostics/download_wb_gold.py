import pandas as pd
import requests

try:
    url = "https://thedocs.worldbank.org/en/doc/5d903e848db1d1b83e0ec8f744e55570-0350012021/related/CMO-Historical-Data-Monthly.xlsx"
    response = requests.get(url)
    with open('cmo.xlsx', 'wb') as f:
        f.write(response.content)
    print("Success")
except Exception as e:
    print(e)
