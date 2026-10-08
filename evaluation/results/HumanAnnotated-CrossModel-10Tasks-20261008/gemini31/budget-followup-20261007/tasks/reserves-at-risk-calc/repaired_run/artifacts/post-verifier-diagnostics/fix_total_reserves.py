import pandas as pd
from openpyxl import load_workbook
import numpy as np

file_path = '/root/output/rar_result.xlsx'
wb = load_workbook(file_path)

# Verify if countries have 2025 total reserve data in 'Total Reserves'. 
# "If a country doesn't have 2025 total reserve data, then delete it from STEP 3 table."
df_total = pd.read_excel(file_path, sheet_name='Total Reserves', header=7)
row_2025_idx = None
for idx, val in enumerate(df_total.iloc[:, 0]):
    if str(val) == '2025':
        row_2025_idx = idx
        break

total_reserves_2025 = {}
if row_2025_idx is not None:
    for col in df_total.columns[2:]:
        country_name = col.split(':')[0].strip()
        val_2025 = df_total.at[row_2025_idx, col]
        if pd.notna(val_2025) and str(val_2025).strip() != '':
            total_reserves_2025[country_name] = float(val_2025)
print("Countries with 2025 total reserves:", list(total_reserves_2025.keys()))
