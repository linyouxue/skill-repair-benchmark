import pandas as pd
import numpy as np

# Load Output File
out_file = 'output/rar_result.xlsx'
out_df = pd.read_excel(out_file, sheet_name=None)
value_df = out_df['Value']
volume_df = out_df['Volume']
answer_sheet = out_df['Answer']

# Find average gold price for Jan-Sep 2025
gold_sheet = out_df['Gold price']
date_col = gold_sheet.columns[0]
price_col = gold_sheet.columns[1]

# Extract 2025 Jan-Sep prices
mask = gold_sheet[date_col].str.startswith('2025M', na=False)
mask_months = gold_sheet[date_col].apply(lambda x: int(str(x).split('M')[1]) if pd.notna(x) and 'M' in str(x) else 99)
mask = mask & (mask_months <= 9)
gold_2025_subset = gold_sheet[mask]
avg_gold_price_2025 = gold_2025_subset[price_col].mean()
print(f"Jan-Sep 2025 Average Gold Price: {avg_gold_price_2025}")

# Get countries from Value sheet with 2025 data
value_2025_row = value_df[value_df['.DESC'].astype(str) == '2025'].iloc[0]
value_countries = {}
for col in value_df.columns[2:]:
    val = value_2025_row[col]
    if pd.notna(val):
        country_name = col.split(':')[0].strip()
        if 'Czechia' in country_name:
            country_name = 'Czechia'
        value_countries[country_name] = float(val)

print("Value countries:", value_countries)

# Get countries from Volume sheet with 2025 data, not in Value sheet
volume_2025_row = volume_df[volume_df['.DESC'].astype(str) == '2025'].iloc[0]
volume_countries = {}
for col in volume_df.columns[2:]:
    val = volume_2025_row[col]
    if pd.notna(val):
        country_name = col.split(':')[0].strip()
        if 'Czechia' in country_name:
            country_name = 'Czechia'
        if country_name not in value_countries:
            volume_countries[country_name] = float(val)

print("Additional Volume countries:", volume_countries)

# Add volume countries to value dictionary by converting volume to value
for country, vol in volume_countries.items():
    col_name = [c for c in volume_df.columns if country in c][0]
    
    if 'Mil.Fine Troy Ounces' in col_name or 'Mil.Troy Ounce' in col_name or 'Mil.Troy.Oz' in col_name or 'Mil.US$' in col_name:
        val = vol * avg_gold_price_2025
    elif 'Thous.Troy Ounce' in col_name:
        val = vol * avg_gold_price_2025 / 1000
    else:
        val = vol * avg_gold_price_2025
        
    value_countries[country] = val

print("Combined value countries:", value_countries)

# STEP 2 filling
step2_start_idx = answer_sheet[answer_sheet['Unnamed: 0'] == 'STEP 2'].index[0]
country_row_idx = answer_sheet[answer_sheet['Unnamed: 0'] == 'Country'].index[0]
reserve_row_idx = answer_sheet[answer_sheet['Unnamed: 0'] == 'Gold reserves \n(in millions of USD)'].index[0]
exposure_row_idx = answer_sheet[answer_sheet['Unnamed: 0'] == 'Gold valuation exposure (95% one-sided shock)'].index[0]

z_score = -1.645 # 95% one-sided shock
latest_3m_vol = gold_sheet['3-month volatility'].dropna().iloc[-1]
shock = (z_score * latest_3m_vol) / 100

for i, (country, val) in enumerate(value_countries.items()):
    col_name = f"Unnamed: {i+1}"
    if col_name not in answer_sheet.columns:
        answer_sheet[col_name] = np.nan
    answer_sheet.loc[country_row_idx, col_name] = country
    answer_sheet.loc[reserve_row_idx, col_name] = val
    answer_sheet.loc[exposure_row_idx, col_name] = val * shock

out_df['Answer'] = answer_sheet

# Save back to check
with pd.ExcelWriter('output/rar_result.xlsx', engine='openpyxl') as writer:
    for sheet_name, df in out_df.items():
        df.to_excel(writer, sheet_name=sheet_name, index=False)
print("Finished Step 2 processing.")
