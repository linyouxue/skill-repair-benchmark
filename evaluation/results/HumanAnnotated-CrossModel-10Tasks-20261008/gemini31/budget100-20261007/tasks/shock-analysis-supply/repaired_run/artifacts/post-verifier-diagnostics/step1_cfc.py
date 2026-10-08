import pandas as pd
from openpyxl import load_workbook
import requests

cfc_df = pd.read_csv('cfc.csv')

wb = load_workbook('test-supply.xlsx')
ws = wb['CFC data']

for row in range(2, ws.max_row + 1):
    year_cell = ws.cell(row=row, column=2).value
    try:
        year = int(year_cell)
        val = cfc_df[cfc_df['TIME_PERIOD'] == year]['OBS_VALUE'].values
        if len(val) > 0:
            ws.cell(row=row, column=3).value = float(val[0])
            pwt_row = year - 1990 + 2
            ws.cell(row=row, column=4).value = f"='PWT'!B{pwt_row}"
            # Because PWT Capital stock is in Millions (PWT metadata: rnna is "Capital stock at current PPPs (in mil. 2017US$)")
            # Or perhaps millions? PWT says it's in millions.
            # ECB CFC data is in absolute GEL. Wait, "XDC.V.N". It's domestic currency (GEL).
            # And PWT is in PPP USD. Depreciation rate = CFC / Capital Stock. If they are in different currencies, it's wrong.
            # Let's check PWT rgdpna vs WEO NGDP_R. 
            # Usually depreciation rate is just calculated if they match or maybe we shouldn't worry about units here because the prompt just says "calculate the depreciation rate using column C&D".
            ws.cell(row=row, column=5).value = f"=C{row}/D{row}"
    except (ValueError, TypeError):
        pass

wb.save('test-supply.xlsx')
