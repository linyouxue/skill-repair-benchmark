import urllib.request
import os

url = "https://dataverse.nl/api/access/datafile/354095" # Try the other one
output_file = "pwt1001.xlsx"

print("Downloading PWT dataset...")
urllib.request.urlretrieve(url, output_file)
print("Download complete.")
