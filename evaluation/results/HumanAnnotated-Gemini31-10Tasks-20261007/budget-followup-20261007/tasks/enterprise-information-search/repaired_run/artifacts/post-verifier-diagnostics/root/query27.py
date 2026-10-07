import json

def search():
    with open('/root/DATA/products/CoachForce.json', 'r') as f:
        data = json.load(f)
    
    docs = data['documents']
    for doc in docs:
        if doc.get('id') == 'latest_cofoaix_market_research_report':
            print("FOUND REPORT latest:")
            print(json.dumps(doc, indent=2))
            
search()
