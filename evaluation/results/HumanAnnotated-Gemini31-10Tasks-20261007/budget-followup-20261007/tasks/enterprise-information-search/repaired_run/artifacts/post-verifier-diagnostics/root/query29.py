import json

def search():
    with open('/root/DATA/products/CoachForce.json', 'r') as f:
        data = json.load(f)
    
    for m in data.get('slack', []):
        if 'market research' in str(m).lower() and 'cofoaix' in str(m).lower():
            if 'cofoaix_market_research_report' in str(m).lower():
                print(f"SLACK ID: {m.get('id')}")
                print(json.dumps(m, indent=2))
            
search()
