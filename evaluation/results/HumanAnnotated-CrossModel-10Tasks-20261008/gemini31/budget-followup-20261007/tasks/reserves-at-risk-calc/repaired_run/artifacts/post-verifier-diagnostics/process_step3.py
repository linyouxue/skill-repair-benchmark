import pandas as pd
from openpyxl import load_workbook
import numpy as np

file_path = '/root/output/rar_result.xlsx'
wb = load_workbook(file_path)

df_total = pd.read_excel(file_path, sheet_name='Total Reserves', header=7)

# We need countries with 2025 data in "Total Reserves"
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

# Read Step 2 results
ws_answer = wb['Answer']
countries_step2 = {}

col = 2 # Column B
while True:
    def get_col_letter(col_num):
        res = ""
        while col_num > 0:
            col_num, rem = divmod(col_num - 1, 26)
            res = chr(65 + rem) + res
        return res
    col_letter = get_col_letter(col)
    country = ws_answer[f'{col_letter}10'].value
    if not country:
        break
    
    countries_step2[country] = {
        'col_letter_step2': col_letter
    }
    col += 1

start_col = 2
curr_col = start_col

for country, data in countries_step2.items():
    if country in total_reserves_2025:
        def get_col_letter(col_num):
            res = ""
            while col_num > 0:
                col_num, rem = divmod(col_num - 1, 26)
                res = chr(65 + rem) + res
            return res
        col_letter = get_col_letter(curr_col)
        
        # Row 20: Country
        ws_answer[f'{col_letter}20'] = country
        
        # Row 21: Gold reserves
        ws_answer[f'{col_letter}21'] = f"={data['col_letter_step2']}11"
        
        # Row 22: Gold valuation exposure
        ws_answer[f'{col_letter}22'] = f"={data['col_letter_step2']}12"
        
        # Row 23: Total Reserve
        # "Use INDEX+MATCH or XLOOKUP to find the relevant country's 2025 data in Total Reserves in row 23"
        # We need to construct an XLOOKUP formula for this.
        # Lookup value: Country name (in row 20)
        # However, the column headers in 'Total Reserves' have suffix like ": International Reserves, Monthly".
        # We can use XLOOKUP with wildcard. E.g. XLOOKUP(B20&"*", 'Total Reserves'!C8:R8, 'Total Reserves'!C17:R17, "", 2)
        # Wait, the data row for 2025 is row 17 (index 16, header is at row 8, data starts at row 9 for 2017)
        # 'Total Reserves' sheet:
        # Row 8 has the headers
        # Row 17 has the 2025 data
        formula = f'=XLOOKUP({col_letter}20&"*", \'Total Reserves\'!$C$8:$R$8, \'Total Reserves\'!$C$17:$R$17, "", 2)'
        ws_answer[f'{col_letter}23'] = formula
        
        # Row 24: RaR
        # RaR = Exposure / Total Reserve * 100
        # If both are in millions USD.
        # Wait, some Total Reserves are in local currency.
        # For Serbia: "Official Reserve Assets (EOP, NSA, Mil.EUR)"
        # For Poland: "Official Reserve Assets (EOP, NSA, Mil.PLN)"
        # But wait, step 3 says: "find the relevant country's 2025 data in 'Total Reserves'". It doesn't mention FX conversion.
        # Let's just do Exposure / Total Reserve. The user hint says: "Calculate RaR in row 24 based on what you have in the STEP 3 table."
        ws_answer[f'{col_letter}24'] = f"={col_letter}22/{col_letter}23*100"
        
        curr_col += 1

wb.save('/root/output/rar_result.xlsx')
print("Step 3 done")
