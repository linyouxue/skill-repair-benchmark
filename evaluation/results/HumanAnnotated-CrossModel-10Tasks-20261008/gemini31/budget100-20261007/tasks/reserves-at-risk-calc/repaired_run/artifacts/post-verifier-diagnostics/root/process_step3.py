import pandas as pd
import numpy as np

out_file = 'output/rar_result.xlsx'
out_df = pd.read_excel(out_file, sheet_name=None)
total_reserves_df = out_df['Total Reserves']
answer_sheet = out_df['Answer']

# Get 2025 total reserves
reserves_2025_row = total_reserves_df[total_reserves_df['.DESC'].astype(str) == '2025'].iloc[0]
reserves_countries = {}
for col in total_reserves_df.columns[2:]:
    val = reserves_2025_row[col]
    if pd.notna(val):
        country_name = col.split(':')[0].strip()
        if 'Czechia' in country_name:
            country_name = 'Czechia'
        if 'Kyrgyz' in country_name:
            country_name = 'Kyrgyz Republic'
        reserves_countries[country_name] = float(val)

print("Total Reserves countries:", reserves_countries)

# STEP 3 processing
country_row_idx2 = answer_sheet[answer_sheet['Unnamed: 0'] == 'Country'].index[0] # Step 2 country row
country_row_idx3 = answer_sheet[answer_sheet['Unnamed: 0'] == 'Country'].index[1] # Step 3 country row

reserve_row_idx2 = answer_sheet[answer_sheet['Unnamed: 0'] == 'Gold reserves \n(in millions of USD)'].index[0]
exposure_row_idx2 = answer_sheet[answer_sheet['Unnamed: 0'] == 'Gold valuation exposure (95% one-sided shock)'].index[0]

reserve_row_idx3 = answer_sheet[answer_sheet['Unnamed: 0'] == 'Gold reserves \n(in millions of USD)'].index[1]
exposure_row_idx3 = answer_sheet[answer_sheet['Unnamed: 0'] == 'Gold valuation exposure (95% one-sided shock)'].index[1]
total_reserve_row_idx3 = answer_sheet[answer_sheet['Unnamed: 0'] == 'Total Reserve'].index[0]
rar_row_idx3 = answer_sheet[answer_sheet['Unnamed: 0'] == 'RaR(in percent of total reserves)'].index[0]

# Clear Step 3 area first (columns from 1 onwards)
for col in answer_sheet.columns[1:]:
    answer_sheet.loc[country_row_idx3, col] = np.nan
    answer_sheet.loc[reserve_row_idx3, col] = np.nan
    answer_sheet.loc[exposure_row_idx3, col] = np.nan
    answer_sheet.loc[total_reserve_row_idx3, col] = np.nan
    answer_sheet.loc[rar_row_idx3, col] = np.nan

# Copy countries that have total reserves in 2025
col_idx = 1
for col in answer_sheet.columns[1:]:
    country = answer_sheet.loc[country_row_idx2, col]
    if pd.notna(country) and country in reserves_countries:
        new_col = f"Unnamed: {col_idx}"
        if new_col not in answer_sheet.columns:
            answer_sheet[new_col] = np.nan
            
        answer_sheet.loc[country_row_idx3, new_col] = country
        answer_sheet.loc[reserve_row_idx3, new_col] = answer_sheet.loc[reserve_row_idx2, col]
        answer_sheet.loc[exposure_row_idx3, new_col] = answer_sheet.loc[exposure_row_idx2, col]
        answer_sheet.loc[total_reserve_row_idx3, new_col] = reserves_countries[country]
        
        exposure = answer_sheet.loc[exposure_row_idx3, new_col]
        total_res = answer_sheet.loc[total_reserve_row_idx3, new_col]
        
        # Exposure is calculated as negative (shock = z_score * vol / 100), if z-score is -1.645
        # So we might want to multiply by 100 for percentage
        answer_sheet.loc[rar_row_idx3, new_col] = (exposure / total_res) * 100
        
        col_idx += 1

out_df['Answer'] = answer_sheet

with pd.ExcelWriter('output/rar_result.xlsx', engine='openpyxl') as writer:
    for sheet_name, df in out_df.items():
        df.to_excel(writer, sheet_name=sheet_name, index=False)
print("Finished Step 3 processing.")
