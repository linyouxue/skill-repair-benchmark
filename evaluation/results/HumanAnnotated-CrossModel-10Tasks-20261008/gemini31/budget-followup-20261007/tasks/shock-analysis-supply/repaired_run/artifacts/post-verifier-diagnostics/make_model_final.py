import pandas as pd
from openpyxl import load_workbook

wb = load_workbook("test-supply.xlsx")

# ==================== STEP 1: data collection ====================
# PWT Data
pwt = pd.read_excel("pwt110.xlsx", sheet_name='Data')
pwt_geo = pwt[pwt['country'] == 'Georgia']
pwt_rnna = dict(zip(pwt_geo['year'], pwt_geo['rnna']))

# Let's see if there is a 'cn' or 'ck' variable or something else we need. 
# Prompt: "fill the relevant data in column B and C in sheet PWT"
# Since only A and B are currently present, maybe we need to add a column C? What could it be? 
# "HINT: read the PWT metadata sheet to understand the meaning of each variable."
# Let's check metadata of PWT
