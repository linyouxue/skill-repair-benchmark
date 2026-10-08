import json

def search():
    with open('/root/DATA/products/CoachForce.json', 'r') as f:
        data = json.load(f)
    
    docs = data['documents']
    for doc in docs:
        if 'Market Research Report' in str(doc).lower() or 'market' in str(doc).lower():
            print("FOUND DOC:")
            print(json.dumps(doc, indent=2))
            
search()
