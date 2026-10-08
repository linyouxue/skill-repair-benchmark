import json

def get_coachforce():
    with open('/root/DATA/products/CoachForce.json', 'r') as f:
        data = json.load(f)
        
    print("\nDocuments for CoachForce Market Research Report:")
    for doc in data.get('documents', []):
        t = doc.get('type', '').lower()
        if 'market' in t or 'research' in t:
            print(f"Doc ID: {doc.get('id')} - Type: {doc.get('type')} - Author: {doc.get('author')}")
            for k, v in doc.items():
                if 'review' in k.lower():
                    print(f"  {k}: {v}")

    print("\nLet's check other product files for CoachForce Market Research Report.")
import os
for f in os.listdir('/root/DATA/products/'):
    with open('/root/DATA/products/'+f, 'r') as file:
        data = json.load(file)
        for doc in data.get('documents', []):
            t = doc.get('type', '').lower()
            if 'market' in t or 'research' in t:
                # Is it about CoachForce?
                if 'coach' in doc.get('content', '').lower() or 'coach' in doc.get('id', '').lower():
                    print(f"Found in {f}: Doc ID: {doc.get('id')} - Type: {doc.get('type')} - Author: {doc.get('author')}")
