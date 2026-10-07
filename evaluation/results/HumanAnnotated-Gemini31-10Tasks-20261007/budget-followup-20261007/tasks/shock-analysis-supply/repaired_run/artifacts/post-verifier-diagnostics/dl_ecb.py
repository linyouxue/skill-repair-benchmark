import urllib.request
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = "https://data-api.ecb.europa.eu/service/data/IDCS/A.N.GE.W0.S1.S1.N.D.P51C._Z._Z._Z.XDC._Z.S.V.N._T?format=csvdata"

try:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, context=ctx) as r:
        content = r.read()
        with open("ecb_data.csv", "wb") as f:
            f.write(content)
        print("Downloaded")
except Exception as e:
    print(e)
