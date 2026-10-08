import pandas as pd
import urllib.request
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req1 = urllib.request.Request("https://www.imf.org/external/datamapper/api/v1/NGDP_R/GEO", headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req1, context=ctx) as r:
        d1 = json.loads(r.read())
        if 'values' in d1 and 'NGDP_R' in d1['values'] and 'GEO' in d1['values']['NGDP_R']:
            ngdp_r = d1['values']['NGDP_R']['GEO']
            print("Found NGDP_R")
except Exception as e:
    print(e)
    
req2 = urllib.request.Request("https://www.imf.org/external/datamapper/api/v1/NGDP_RPCH/GEO", headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req2, context=ctx) as r:
        d2 = json.loads(r.read())
        if 'values' in d2 and 'NGDP_RPCH' in d2['values'] and 'GEO' in d2['values']['NGDP_RPCH']:
            ngdp_rpch = d2['values']['NGDP_RPCH']['GEO']
            print("Found NGDP_RPCH")
except Exception as e:
    print(e)

df = pd.DataFrame({
    'year': list(ngdp_r.keys()),
    'NGDP_R': list(ngdp_r.values())
})
df2 = pd.DataFrame({
    'year': list(ngdp_rpch.keys()),
    'NGDP_RPCH': list(ngdp_rpch.values())
})

merged = pd.merge(df, df2, on='year', how='outer')
merged['year'] = pd.to_numeric(merged['year'])
merged = merged[(merged['year'] >= 2000) & (merged['year'] <= 2027)].sort_values('year')
merged.to_csv('geo_weo.csv', index=False)
print("Saved geo_weo.csv")
