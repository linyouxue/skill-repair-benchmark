import pandas as pd

# 1. Get PWT data
pwt = pd.read_stata('pwt1001.xlsx')

# Filter for Georgia
pwt_geo = pwt[pwt['country'] == 'Georgia']
pwt_geo = pwt_geo[['year', 'rnna']]

print(pwt_geo.head())

