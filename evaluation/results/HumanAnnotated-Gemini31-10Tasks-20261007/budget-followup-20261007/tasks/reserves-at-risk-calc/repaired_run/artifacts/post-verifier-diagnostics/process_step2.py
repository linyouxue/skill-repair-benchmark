import pandas as pd
from openpyxl import load_workbook
import numpy as np

file_path = '/root/output/rar_result.xlsx'
wb = load_workbook(file_path)

df_value = pd.read_excel(file_path, sheet_name='Value', header=7)
df_volume = pd.read_excel(file_path, sheet_name='Volume', header=7)
df_gold = pd.read_excel(file_path, sheet_name='Gold price')

# Find the 2025 Jan-Sep average gold price
gold_2025 = df_gold[df_gold['Unnamed: 0'].isin([f'2025M{i}' for i in range(1, 10)])]
# We wrote Gold_Price into column B which corresponds to index 1 or column 'Gold_Price' is not in this df_gold read maybe if it was saved by openpyxl without calculating values? Wait. 
# Pandas read_excel on openpyxl output might read formulas. We used actual values for gold price in process_step1.py!
# Let's check Gold price in column 'Gold, Fixing...' (idx 1). 
gold_prices_2025 = gold_2025.iloc[:, 1].dropna().astype(float)
gold_price_2025_avg = gold_prices_2025.mean()
print('2025 Jan-Sep avg gold price:', gold_price_2025_avg)

# Countries with 2025 data in sheet "Value"
# First find the row index for 2025 in df_value (header=7 means row 8 is header)
# index 0 is 2017, index 8 is 2025
row_2025_idx = None
for idx, val in enumerate(df_value.iloc[:, 0]):
    if str(val) == '2025':
        row_2025_idx = idx
        break

countries_with_value_2025 = {}
if row_2025_idx is not None:
    for col in df_value.columns[2:]:
        country_name = col.split(':')[0].strip()
        val_2025 = df_value.at[row_2025_idx, col]
        if pd.notna(val_2025) and str(val_2025).strip() != '':
            countries_with_value_2025[country_name] = float(val_2025)

row_2025_idx_vol = None
for idx, val in enumerate(df_volume.iloc[:, 0]):
    if str(val) == '2025':
        row_2025_idx_vol = idx
        break

if row_2025_idx_vol is not None:
    for col in df_volume.columns[2:]:
        country_name = col.split(':')[0].strip()
        val_2025 = df_volume.at[row_2025_idx_vol, col]
        if pd.notna(val_2025) and str(val_2025).strip() != '':
            if country_name not in countries_with_value_2025:
                vol = float(val_2025)
                # Check units from column name
                if 'Thous' in col or 'Thous.' in col:
                    vol = vol / 1000.0 # convert to millions
                
                value = vol * gold_price_2025_avg
                countries_with_value_2025[country_name] = value

print("Countries mapped:", countries_with_value_2025)

ws_answer = wb['Answer']
start_col = 2 # Column B

for i, (country, value) in enumerate(countries_with_value_2025.items()):
    col_idx = start_col + i
    def get_col_letter(col_num):
        res = ""
        while col_num > 0:
            col_num, rem = divmod(col_num - 1, 26)
            res = chr(65 + rem) + res
        return res
    
    col_letter = get_col_letter(col_idx)
    
    ws_answer[f'{col_letter}10'] = country
    ws_answer[f'{col_letter}11'] = value
    ws_answer[f'{col_letter}12'] = f"={col_letter}11*$B$2*$B$4/100"

wb.save('/root/output/rar_result.xlsx')
print("Step 2 done")
