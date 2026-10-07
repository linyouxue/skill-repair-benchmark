import urllib.request
import json
import pandas as pd
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

try:
    req = urllib.request.Request("https://data-api.ecb.europa.eu/service/data/EXR/A.GEL.EUR.SP00.A?format=csvdata")
    with urllib.request.urlopen(req, context=ctx) as r:
        print(r.read()[:100])
except Exception as e:
    print(e)
