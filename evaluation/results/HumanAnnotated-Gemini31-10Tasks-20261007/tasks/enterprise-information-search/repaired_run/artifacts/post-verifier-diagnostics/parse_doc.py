import json

with open('/root/DATA/products/CoachForce.json', 'r') as f:
    data = json.load(f)

for doc in data.get('documents', []):
    if doc.get('id') == 'latest_cofoaix_market_research_report':
        print(doc)
