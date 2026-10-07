import urllib.request
import json
import pandas as pd

url = "https://www.imf.org/external/np/res/commod/ExternalData.csv" 
# Oh wait, IMF has an official monthly CSV/Excel we tried to get. Let's try to fetch another url.
url = "https://www.imf.org/-/media/Files/Research/CommodityPrices/Monthly/PCOMM_Data.xlsx"
