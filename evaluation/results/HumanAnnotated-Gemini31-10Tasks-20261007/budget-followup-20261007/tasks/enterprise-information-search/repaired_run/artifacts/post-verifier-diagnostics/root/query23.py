import json

def search():
    with open('/root/DATA/products/PersonalizeForce.json', 'r') as f:
        data = json.load(f)
    
    for m in data.get('slack', []):
        if 'competitor' in str(m).lower() or 'strength' in str(m).lower() or 'weakness' in str(m).lower() or 'tailorai' in str(m).lower() or 'personaai' in str(m).lower() or 'smartsuggest' in str(m).lower():
            if 'strength' in str(m).lower() or 'weakness' in str(m).lower():
                print(f"SLACK: {m.get('id')}")
                print(json.dumps(m, indent=2))
            
search()
