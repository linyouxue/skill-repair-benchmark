import urllib.request
import urllib.parse
from html.parser import HTMLParser
import json
import pandas as pd

url = "https://www.imf.org/external/datamapper/api/v1/NGDP_RPCH/GEO"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode('utf-8'))
        print(data['values']['NGDP_RPCH']['GEO'])
except Exception as e:
    print(e)
