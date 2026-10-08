import pandas as pd
excel_file = "test-supply.xlsx"
sheets = pd.ExcelFile(excel_file).sheet_names
print("Sheets:", sheets)
