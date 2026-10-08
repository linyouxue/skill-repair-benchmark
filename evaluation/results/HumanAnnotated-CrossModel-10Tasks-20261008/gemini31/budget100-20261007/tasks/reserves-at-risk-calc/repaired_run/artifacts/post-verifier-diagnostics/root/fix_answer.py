import pandas as pd
import numpy as np
out_file = 'output/rar_result.xlsx'
out_df = pd.read_excel(out_file, sheet_name=None)
ans = out_df['Answer']

avg_gold_price_2025 = 3202.823608235561
value_countries = {'Belarus': 7471.0, 'Georgia': 1002.0, 'Moldova': 10.71, 'Ukraine': 3877.64, 'Uzbekistan': 55092.42, 'Czechia': 10121.89, 'Latvia': 921.28, 'Lithuania': 807.1}
vol_countries = {'Slovakia': 1.019}
for k, v in vol_countries.items():
    value_countries[k] = v * avg_gold_price_2025

z_score = -1.645
latest_3m_vol = 3.829124458897042
shock = (z_score * latest_3m_vol) / 100

# Fix indexing for STEP 2 (we know Country is row 9 based on the output, index 9)
country_row_idx2 = 9
reserve_row_idx2 = 10
exposure_row_idx2 = 11

for i, (country, val) in enumerate(value_countries.items()):
    col_name = f"Unnamed: {i+2}"
    if col_name not in ans.columns:
        ans[col_name] = np.nan
    ans.loc[country_row_idx2, col_name] = country
    ans.loc[reserve_row_idx2, col_name] = val
    ans.loc[exposure_row_idx2, col_name] = val * shock

reserves_countries = {'Armenia': 5086.3, 'Belarus': 14425.9, 'Georgia': 6158.7, 'Kazakhstan': 65727.0, 'Moldova': 5999.34, 'Uzbekistan': 66311.75, 'Czechia': 175830.49, 'Latvia': 6076.9, 'Lithuania': 7082.7}

country_row_idx3 = 18
reserve_row_idx3 = 19
exposure_row_idx3 = 20
total_reserve_row_idx3 = 21
rar_row_idx3 = 22

col_idx = 2
for k, v in value_countries.items():
    if k in reserves_countries:
        col_name = f"Unnamed: {col_idx}"
        ans.loc[country_row_idx3, col_name] = k
        ans.loc[reserve_row_idx3, col_name] = v
        ans.loc[exposure_row_idx3, col_name] = v * shock
        ans.loc[total_reserve_row_idx3, col_name] = reserves_countries[k]
        
        exposure = ans.loc[exposure_row_idx3, col_name]
        total_res = ans.loc[total_reserve_row_idx3, col_name]
        ans.loc[rar_row_idx3, col_name] = (exposure / total_res) * 100
        col_idx += 1

# Make sure STEP 1 values are set correctly
ans.loc[1, 'STEP 1'] = -1.645
ans.loc[2, 'STEP 1'] = 3.829124458897042
ans.loc[3, 'STEP 1'] = 3.829124458897042 * np.sqrt(12)
ans.loc[4, 'STEP 1'] = 3.856983893339199

out_df['Answer'] = ans
with pd.ExcelWriter('output/rar_result.xlsx', engine='openpyxl') as writer:
    for sheet_name, df in out_df.items():
        df.to_excel(writer, sheet_name=sheet_name, index=False)
