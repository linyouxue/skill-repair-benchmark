import json

def search():
    with open('/root/DATA/products/CoachForce.json', 'r') as f:
        data = json.load(f)
    
    for p in data.get('prs', []):
        if 'latest_cofoaix_market_research_report' in str(p) or 'cofoaix_market_research_report' in str(p):
            print(f"PR: {p.get('id')}, title: {p.get('title')}, reviewers: {p.get('reviewers')}")
            
search()
