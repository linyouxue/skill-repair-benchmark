import json

def search():
    with open('/root/DATA/products/PersonalizeForce.json', 'r') as f:
        data = json.load(f)
    
    docs = data['documents']
    for doc in docs:
        if 'competitor' in str(doc).lower() or 'strength' in str(doc).lower() or 'weakness' in str(doc).lower():
            if 'strength' in str(doc).lower() and 'weakness' in str(doc).lower():
                print(f"DOC: {doc.get('id')}")
                print(json.dumps(doc, indent=2))
            
search()
