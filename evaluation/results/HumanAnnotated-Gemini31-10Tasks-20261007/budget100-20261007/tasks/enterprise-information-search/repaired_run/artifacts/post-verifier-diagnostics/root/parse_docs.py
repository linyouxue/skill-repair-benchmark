import json
import os

for filename in os.listdir('/root/DATA/products/'):
    if not filename.endswith('.json'):
        continue
    with open('/root/DATA/products/' + filename, 'r') as f:
        data = json.load(f)

    for doc in data.get('documents', []):
        if 'Market Research' in doc.get('title', '') or 'Market Research' in doc.get('document_type', '') or 'Market Research' in doc.get('content', ''):
            print(f"FILE: {filename}")
            print("DOC ID:", doc.get('doc_id'))
            print("TITLE:", doc.get('title'))
            print("TYPE:", doc.get('document_type'))
            print("AUTHOR:", doc.get('author'))
            print("REVIEWERS:", doc.get('reviewers'))
            print("KEY REVIEWERS:", doc.get('key_reviewers'))
            print("---")
