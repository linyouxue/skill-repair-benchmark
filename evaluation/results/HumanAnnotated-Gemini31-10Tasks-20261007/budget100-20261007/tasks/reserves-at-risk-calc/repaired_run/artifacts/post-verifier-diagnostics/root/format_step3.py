import pandas as pd
import numpy as np

# Let's fix STEP 3 indexing
out_file = 'output/rar_result.xlsx'
out_df = pd.read_excel(out_file, sheet_name=None)
ans = out_df['Answer']

country_row_idx2 = ans[ans['Unnamed: 0'] == 'Country'].index[0]
reserve_row_idx2 = ans[ans['Unnamed: 0'] == 'Gold reserves \n(in millions of USD)'].index[0]
exposure_row_idx2 = ans[ans['Unnamed: 0'] == 'Gold valuation exposure (95% one-sided shock)'].index[0]

country_row_idx3 = ans[ans['Unnamed: 0'] == 'Country'].index[1]
reserve_row_idx3 = ans[ans['Unnamed: 0'] == 'Gold reserves \n(in millions of USD)'].index[1]
exposure_row_idx3 = ans[ans['Unnamed: 0'] == 'Gold valuation exposure (95% one-sided shock)'].index[1]
total_reserve_row_idx3 = ans[ans['Unnamed: 0'] == 'Total Reserve'].index[0]
rar_row_idx3 = ans[ans['Unnamed: 0'] == 'RaR(in percent of total reserves)'].index[0]

print("Indices Step 3:", country_row_idx3, reserve_row_idx3, exposure_row_idx3, total_reserve_row_idx3, rar_row_idx3)
