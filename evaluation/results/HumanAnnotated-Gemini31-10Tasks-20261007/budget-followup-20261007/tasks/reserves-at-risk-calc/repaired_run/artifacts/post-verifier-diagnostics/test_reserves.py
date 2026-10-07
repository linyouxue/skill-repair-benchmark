import pandas as pd
df = pd.read_excel('/root/output/rar_result.xlsx', sheet_name='Total Reserves', header=7)
row_2025_idx = None
for idx, val in enumerate(df.iloc[:, 0]):
    if str(val) == '2025':
        row_2025_idx = idx
        break
for col in df.columns[2:]:
    val_2025 = df.at[row_2025_idx, col]
    if pd.notna(val_2025) and str(val_2025).strip() != '':
        print(f"{col}: {val_2025}")
