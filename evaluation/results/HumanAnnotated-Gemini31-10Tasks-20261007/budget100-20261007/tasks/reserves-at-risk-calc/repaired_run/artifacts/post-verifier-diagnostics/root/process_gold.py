import pandas as pd
import numpy as np

# Load Output File
out_file = 'output/rar_result.xlsx'
out_df = pd.read_excel(out_file, sheet_name=None)
gold_sheet = out_df['Gold price']
date_col = gold_sheet.columns[0]
price_col = gold_sheet.columns[1]

# Load IMF Data
imf_df = pd.read_excel('External-Data.xlsx', header=0)
imf_data = imf_df.iloc[3:][['Commodity', 'PGOLD']].copy()
imf_data.columns = ['Month', 'Gold Price']
imf_data['Month'] = imf_data['Month'].astype(str)
imf_data['Gold Price'] = pd.to_numeric(imf_data['Gold Price'], errors='coerce')
imf_data = imf_data.dropna(subset=['Gold Price'])

# Merge data
gold_sheet[date_col] = gold_sheet[date_col].astype(str)
merged = pd.merge(gold_sheet[[date_col]], imf_data, left_on=date_col, right_on='Month', how='left')
gold_sheet[price_col] = merged['Gold Price']

# Calculate log returns
prices = gold_sheet[price_col].values
log_returns = np.full_like(prices, np.nan)
for i in range(1, len(prices)):
    if not np.isnan(prices[i]) and not np.isnan(prices[i-1]) and prices[i-1] > 0:
        log_returns[i] = np.log(prices[i] / prices[i-1]) * 100

gold_sheet['Monthly log return'] = log_returns

# Calculate volatilities
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

# Step 1 Answers
answer_sheet = out_df['Answer']
latest_3m_vol = vol_3m[~np.isnan(vol_3m)][-1]
latest_12m_vol = vol_12m[~np.isnan(vol_12m)][-1]
z_score = -1.645 # 95% one-sided

answer_sheet.loc[answer_sheet['Unnamed: 0'] == 'Z-score (95% one-sided)', 'STEP 1'] = z_score
answer_sheet.loc[answer_sheet['Unnamed: 0'] == '3-month volatility', 'STEP 1'] = latest_3m_vol
answer_sheet.loc[answer_sheet['Unnamed: 0'] == '3-month volatility annualized', 'STEP 1'] = latest_3m_vol * np.sqrt(12)
answer_sheet.loc[answer_sheet['Unnamed: 0'] == '12-month volatility', 'STEP 1'] = latest_12m_vol

out_df['Answer'] = answer_sheet

# Save back to check
with pd.ExcelWriter('output/rar_result.xlsx', engine='openpyxl') as writer:
    for sheet_name, df in out_df.items():
        df.to_excel(writer, sheet_name=sheet_name, index=False)
print("Finished Step 1 processing.")
