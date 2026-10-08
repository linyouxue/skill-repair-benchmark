import json

def search():
    with open('/root/DATA/products/PersonalizeForce.json', 'r') as f:
        data = json.load(f)
    print("Loaded PersonalizeForce.json")
    
    docs = data['documents']
    for doc in docs:
        if doc.get('id') in ['personalizeforce_competitor_analysis', 'final_personalizeforce_competitor_analysis', 'latest_personalizeforce_competitor_analysis']:
            print(f"DOC: {doc.get('id')}")
            print(json.dumps(doc, indent=2))
            
search()
