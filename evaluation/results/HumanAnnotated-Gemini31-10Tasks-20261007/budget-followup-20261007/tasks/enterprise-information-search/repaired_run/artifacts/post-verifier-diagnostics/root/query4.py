import json

def search():
    with open('/root/DATA/products/CoachForce.json', 'r') as f:
        data = json.load(f)
    
    docs = data['documents']
    for doc in docs:
        if 'market research' in str(doc).lower() and doc.get('type') == 'Market Research Report':
            print(f"REPORT ID: {doc.get('id')}, content: {doc.get('content')[:100]}")
            
search()
