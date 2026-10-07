import json
import os

for filename in os.listdir('/root/DATA/products/'):
    if not filename.endswith('.json'): continue
    with open(f'/root/DATA/products/{filename}') as f:
        data = json.load(f)
    for doc in data.get('documents', []):
        doc_str = json.dumps(doc).lower()
        if 'market research' in doc_str:
            print(f"FOUND IN {filename}:", doc.get('doc_id'), doc.get('title'), doc.get('document_type'))
            print(json.dumps(doc, indent=2)[:300])
