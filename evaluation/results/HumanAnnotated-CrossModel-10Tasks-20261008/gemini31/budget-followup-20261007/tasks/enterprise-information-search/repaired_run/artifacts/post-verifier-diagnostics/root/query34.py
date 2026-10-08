import json

def search():
    with open('/root/DATA/products/CoachForce.json', 'r') as f:
        data = json.load(f)
    
    for m in data.get('slack', []):
        if 'latest_cofoaix_market_research_report' in str(m).lower():
            print("FOUND SLACK:")
            print(json.dumps(m, indent=2))
            
search()
