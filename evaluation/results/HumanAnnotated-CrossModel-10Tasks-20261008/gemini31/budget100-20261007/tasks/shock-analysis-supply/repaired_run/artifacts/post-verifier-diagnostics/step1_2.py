import pandas as pd
from openpyxl import load_workbook
import requests

# Let's get the data from API for Georgia
url_rpch = 'https://www.imf.org/external/datamapper/api/v1/NGDP_RPCH/GEO'
r_rpch = requests.get(url_rpch)
rpch_data = r_rpch.json()['values']['NGDP_RPCH']['GEO']

wb = load_workbook('test-supply.xlsx')
ws = wb['WEO_Data']

val_2027 = float(rpch_data['2027'])

for row in range(2, 60): 
    year_cell = ws.cell(row=row, column=2).value
    try:
        year = int(year_cell)
        if str(year) in rpch_data:
            ws.cell(row=row, column=4).value = float(rpch_data[str(year)])
        elif year > 2027:
            ws.cell(row=row, column=4).value = val_2027
    except (ValueError, TypeError):
        pass

# WEO_Data sheet column C contains "NGDP_R", we can't find it in datamapper API directly for Georgia. 
# PWT data for real gdp (rgdpna) can serve as real GDP base. Let's see if we should use formulas.
for row in range(2, 60):
    year_cell = ws.cell(row=row, column=2).value
    try:
        year = int(year_cell)
        if year >= 2001:
            ws.cell(row=row, column=3).value = f"=C{row-1}*(1+D{row}/100)"
    except (ValueError, TypeError):
        pass

wb.save('test-supply.xlsx')
