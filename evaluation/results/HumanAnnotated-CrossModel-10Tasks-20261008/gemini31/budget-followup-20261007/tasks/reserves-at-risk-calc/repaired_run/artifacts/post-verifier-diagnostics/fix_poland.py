import pandas as pd
df_val = pd.read_excel('/root/output/rar_result.xlsx', sheet_name='Value', header=7)
df_vol = pd.read_excel('/root/output/rar_result.xlsx', sheet_name='Volume', header=7)

row_2025 = None
for idx, val in enumerate(df_val.iloc[:, 0]):
    if str(val) == '2025':
        row_2025 = idx
        break

for col in df_val.columns[2:]:
    val = df_val.at[row_2025, col]
    if pd.notna(val) and str(val).strip() != '':
        print(f"Value: {col}: {val}")

row_2025_vol = None
for idx, val in enumerate(df_vol.iloc[:, 0]):
    if str(val) == '2025':
        row_2025_vol = idx
        break

for col in df_vol.columns[2:]:
    val = df_vol.at[row_2025_vol, col]
    if pd.notna(val) and str(val).strip() != '':
        print(f"Volume: {col}: {val}")
