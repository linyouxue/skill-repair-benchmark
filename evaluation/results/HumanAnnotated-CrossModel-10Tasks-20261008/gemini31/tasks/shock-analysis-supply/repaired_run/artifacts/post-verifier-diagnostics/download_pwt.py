import urllib.request
import os

url = "https://dataverse.nl/api/access/datafile/354098" # PWT 10.01 Excel file
output_file = "pwt1001.xlsx"

print("Downloading PWT dataset...")
urllib.request.urlretrieve(url, output_file)
print("Download complete.")
