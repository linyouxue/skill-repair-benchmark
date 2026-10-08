import pandas as pd
from openpyxl import load_workbook
wb = load_workbook("test-supply.xlsx")
# Wait, if PWT data is missing for 2020-2023, maybe the instruction implies we calculate it somehow, or we can use another variable from WEO? No, WEO doesn't have capital stock.
# The instruction says: "latest K is 2023 and latest Y is 2025" and "Get the PWT database ... and fill the relevant data in column B and C in sheet 'PWT'. HINT: read the PWT metadata sheet to understand the meaning of each variable."
# Wait! PWT 10.01 ends in 2019. Did they mean another PWT version? E.g. PWT 10.0?
# The link is https://www.rug.nl/ggdc/productivity/pwt/?lang=en. Maybe there's a newer version? PWT 10.01 is the latest on the main page. Wait, PWT 10.01 was released in Jan 2023. It ends in 2019.
# Let's read the instruction carefully: "Link the capital stock data from "PWT", and calculate the depreciation rate using column C&D"
