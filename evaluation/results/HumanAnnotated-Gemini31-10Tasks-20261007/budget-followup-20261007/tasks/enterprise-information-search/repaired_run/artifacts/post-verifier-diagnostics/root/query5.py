import json
import os

def search():
    for f_name in os.listdir('/root/DATA/products'):
        if not f_name.endswith('.json'):
            continue
        with open(f'/root/DATA/products/{f_name}', 'r') as f:
            data = json.load(f)
            
        docs = data.get('documents', [])
        for doc in docs:
            if doc.get('type') == 'Market Research Report' and 'coachforce' in str(doc).lower():
                print(f"File: {f_name}, REPORT ID: {doc.get('id')}, content: {doc.get('content')[:100]}")
            
search()
