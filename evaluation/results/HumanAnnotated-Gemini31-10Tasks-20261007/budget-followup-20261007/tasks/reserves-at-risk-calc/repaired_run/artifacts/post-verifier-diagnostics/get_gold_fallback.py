import urllib.request
import json
import pandas as pd
import yfinance as yf

# For 2025M6, there's missing data in yfinance. Wait, maybe the date is not matching correctly. Let's interpolate it or forward fill.
# The user asked to calculate 3-month and 12-month volatility. Let's write the whole logic to an openpyxl script.
