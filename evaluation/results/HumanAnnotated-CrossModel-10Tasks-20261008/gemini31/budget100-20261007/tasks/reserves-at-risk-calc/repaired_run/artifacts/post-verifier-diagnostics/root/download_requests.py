import requests

url = 'https://www.imf.org/-/media/files/research/commodityprices/monthly/external-data.xlsx'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
}

session = requests.Session()
response = session.get('https://www.imf.org/en/research/commodity-prices', headers=headers)
print(f"Index status: {response.status_code}")

response = session.get(url, headers=headers)
print(f"Download status: {response.status_code}")

if response.status_code == 200:
    content = response.content
    if content.startswith(b'PK\x03\x04'):
        with open('imf_external_data.xlsx', 'wb') as f:
            f.write(content)
        print('Success! Valid ZIP/XLSX signature.')
    else:
        print('Downloaded content is not a valid XLSX/ZIP file. First 100 bytes:')
        print(content[:100])
