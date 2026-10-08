import pandas as pd
from openpyxl import load_workbook

wb = load_workbook("test-supply.xlsx")

# 1. PWT Data
pwt = pd.read_excel("pwt110.xlsx", sheet_name='Data')
pwt_geo = pwt[pwt['country'] == 'Georgia']
pwt_rnna = dict(zip(pwt_geo['year'], pwt_geo['rnna']))

pwt_sheet = wb['PWT']
# wait, what if column C is meant to be some other variable from PWT? The prompt says: "fill the relevant data in column B and C in sheet PWT. HINT: read the PWT metadata sheet to understand the meaning of each variable."
# Wait, "test-supply.xlsx" PWT sheet might have a header in C! Let's check the first row of PWT.
