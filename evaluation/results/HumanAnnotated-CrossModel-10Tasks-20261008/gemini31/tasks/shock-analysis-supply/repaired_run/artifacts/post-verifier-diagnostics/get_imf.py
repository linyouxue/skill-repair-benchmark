import urllib.request

url = "https://www.imf.org/-/media/Files/Publications/WEO/WEO-Database/2023/WEOOct2023all.xlsx"
output_file = "weo.xlsx"

print("Downloading WEO dataset...")
try:
    urllib.request.urlretrieve(url, output_file)
    print("Download complete.")
except Exception as e:
    print("Failed to download:", e)
