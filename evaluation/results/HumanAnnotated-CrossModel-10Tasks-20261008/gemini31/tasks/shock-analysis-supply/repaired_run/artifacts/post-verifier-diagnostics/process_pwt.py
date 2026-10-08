import pandas as pd

pwt_df = pd.read_excel('pwt1001.xlsx', sheet_name='Data')
geo_df = pwt_df[pwt_df['countrycode'] == 'GEO'].copy()

# The relevant columns in PWT sheet are year, rnna (capital stock), labsh (share of labour compensation)
# We need to fill column B (rnna) and column C (labsh) in the 'PWT' sheet for the corresponding years.
print("Columns in PWT dataset:", pwt_df.columns)
print("GEO data:")
print(geo_df[['year', 'rnna', 'labsh', 'rgdpna', 'ccon']].tail())

