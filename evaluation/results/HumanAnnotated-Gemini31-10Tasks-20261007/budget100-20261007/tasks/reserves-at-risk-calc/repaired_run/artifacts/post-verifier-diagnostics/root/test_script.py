import pandas as pd
import requests
import io
import time

def get_imf_data():
    url = "https://www.imf.org/-/media/files/research/commodityprices/monthly/external-data.xlsx"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    for _ in range(3):
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            if b'errorSource' in response.content[:100]:
                print(f"Content shows error: {response.content[:100]}")
                time.sleep(5)
                continue
            with open("imf_external_data.xlsx", "wb") as f:
                f.write(response.content)
            print("Successfully downloaded imf_external_data.xlsx")
            return
        elif response.status_code == 429:
            print("Rate limited. Waiting 10s...")
            time.sleep(10)
        else:
            print(f"Error: {response.status_code}")
            time.sleep(5)

get_imf_data()
