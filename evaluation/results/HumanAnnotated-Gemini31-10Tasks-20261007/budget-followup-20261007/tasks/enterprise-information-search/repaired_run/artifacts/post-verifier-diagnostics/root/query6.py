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
            if doc.get('type') == 'Market Research Report':
                if 'coachforce' in str(doc).lower() or f_name == 'CoachForce.json':
                    print(f"File: {f_name}, REPORT ID: {doc.get('id')}, doc_link: {doc.get('document_link')}")
            
search()
