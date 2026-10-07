import pandas as pd
import numpy as np

# In previous run, `Unnamed: 0` values were lost. Let's fix this by recreating the whole file from the original test file
import shutil
shutil.copy('data/test-rar.xlsx', 'output/rar_result.xlsx')

out_file = 'output/rar_result.xlsx'
out_df = pd.read_excel(out_file, sheet_name=None)
ans = out_df['Answer']

# Let's verify Unnamed: 0 exists
print("Original Answer 'Unnamed: 0':")
print(ans['Unnamed: 0'].values)

avg_gold_price_2025 = 3202.823608235561
value_countries = {'Belarus': 7471.0, 'Georgia': 1002.0, 'Moldova': 10.71, 'Ukraine': 3877.64, 'Uzbekistan': 55092.42, 'Czechia': 10121.89, 'Latvia': 921.28, 'Lithuania': 807.1}
vol_countries = {'Slovakia': 1.019}
for k, v in vol_countries.items():
    value_countries[k] = v * avg_gold_price_2025

z_score = -1.645
latest_3m_vol = 3.829124458897042
shock = (z_score * latest_3m_vol) / 100

country_row_idx2 = ans[ans['Unnamed: 0'] == 'Country'].index[0]
reserve_row_idx2 = ans[ans['Unnamed: 0'] == 'Gold reserves \n(in millions of USD)'].index[0]
exposure_row_idx2 = ans[ans['Unnamed: 0'] == 'Gold valuation exposure (95% one-sided shock)'].index[0]

for i, (country, val) in enumerate(value_countries.items()):
    col_name = f"Unnamed: {i+1}"
    if col_name not in ans.columns:
        ans[col_name] = np.nan
    ans.loc[country_row_idx2, col_name] = country
    ans.loc[reserve_row_idx2, col_name] = val
    ans.loc[exposure_row_idx2, col_name] = val * shock

reserves_countries = {'Armenia': 5086.3, 'Belarus': 14425.9, 'Georgia': 6158.7, 'Kazakhstan': 65727.0, 'Moldova': 5999.34, 'Uzbekistan': 66311.75, 'Czechia': 175830.49, 'Latvia': 6076.9, 'Lithuania': 7082.7}

country_row_idx3 = ans[ans['Unnamed: 0'] == 'Country'].index[1]
reserve_row_idx3 = ans[ans['Unnamed: 0'] == 'Gold reserves \n(in millions of USD)'].index[1]
exposure_row_idx3 = ans[ans['Unnamed: 0'] == 'Gold valuation exposure (95% one-sided shock)'].index[1]
total_reserve_row_idx3 = ans[ans['Unnamed: 0'] == 'Total Reserve'].index[0]
rar_row_idx3 = ans[ans['Unnamed: 0'] == 'RaR(in percent of total reserves)'].index[0]

col_idx = 1
for k, v in value_countries.items():
    if k in reserves_countries:
        col_name = f"Unnamed: {col_idx}"
        if col_name not in ans.columns:
            ans[col_name] = np.nan
        ans.loc[country_row_idx3, col_name] = k
        ans.loc[reserve_row_idx3, col_name] = v
        ans.loc[exposure_row_idx3, col_name] = v * shock
        ans.loc[total_reserve_row_idx3, col_name] = reserves_countries[k]
        
        exposure = ans.loc[exposure_row_idx3, col_name]
        total_res = ans.loc[total_reserve_row_idx3, col_name]
        ans.loc[rar_row_idx3, col_name] = (exposure / total_res) * 100
        col_idx += 1

ans.loc[1, 'STEP 1'] = -1.645
ans.loc[2, 'STEP 1'] = 3.829124458897042
ans.loc[3, 'STEP 1'] = 3.829124458897042 * np.sqrt(12)
ans.loc[4, 'STEP 1'] = 3.856983893339199

out_df['Answer'] = ans

# Wait, we need to redo Step 1 since we copied over it. No, we just need to run process_gold again?
# Actually, the gold_sheet is the original one from test-rar. Let's load the data from IMF and recalculate gold sheet.

# Re-run gold processing
gold_sheet = out_df['Gold price']
date_col = gold_sheet.columns[0]
price_col = gold_sheet.columns[1]

imf_df = pd.read_excel('External-Data.xlsx', header=0)
imf_data = imf_df.iloc[3:][['Commodity', 'PGOLD']].copy()
imf_data.columns = ['Month', 'Gold Price']
imf_data['Month'] = imf_data['Month'].astype(str)
imf_data['Gold Price'] = pd.to_numeric(imf_data['Gold Price'], errors='coerce')
imf_data = imf_data.dropna(subset=['Gold Price'])

gold_sheet[date_col] = gold_sheet[date_col].astype(str)
merged = pd.merge(gold_sheet[[date_col]], imf_data, left_on=date_col, right_on='Month', how='left')
gold_sheet[price_col] = merged['Gold Price']

prices = gold_sheet[price_col].values
log_returns = np.full_like(prices, np.nan)
for i in range(1, len(prices)):
    if not np.isnan(prices[i]) and not np.isnan(prices[i-1]) and prices[i-1] > 0:
        log_returns[i] = np.log(prices[i] / prices[i-1]) * 100

gold_sheet['Monthly log return'] = log_returns

vol_3m = np.full_like(prices, np.nan)
vol_12m = np.full_like(prices, np.nan)

for i in range(len(log_returns)):
    if i >= 2:
        window_3m = log_returns[i-2:i+1]
        if not np.isnan(window_3m).any():
            vol_3m[i] = np.std(window_3m, ddof=1)
            
    if i >= 11:
        window_12m = log_returns[i-11:i+1]
        if not np.isnan(window_12m).any():
            vol_12m[i] = np.std(window_12m, ddof=1)

gold_sheet['3-month volatility'] = vol_3m
gold_sheet['12-month volatility'] = vol_12m

out_df['Gold price'] = gold_sheet

with pd.ExcelWriter('output/rar_result.xlsx', engine='openpyxl') as writer:
    for sheet_name, df in out_df.items():
        df.to_excel(writer, sheet_name=sheet_name, index=False)
