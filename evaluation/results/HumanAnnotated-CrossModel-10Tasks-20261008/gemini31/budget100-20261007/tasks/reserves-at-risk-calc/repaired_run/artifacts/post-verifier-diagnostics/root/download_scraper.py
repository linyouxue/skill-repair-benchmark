import cloudscraper

url = 'https://www.imf.org/-/media/files/research/commodityprices/monthly/external-data.xlsx'
scraper = cloudscraper.create_scraper()

print("Attempting to download...")
response = scraper.get(url)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    content = response.content
    if content.startswith(b'PK\x03\x04'):
        with open('imf_external_data.xlsx', 'wb') as f:
            f.write(content)
        print('Success! Valid ZIP/XLSX signature.')
    else:
        print('Downloaded content is not a valid XLSX/ZIP file. First 100 bytes:')
        print(content[:100])
