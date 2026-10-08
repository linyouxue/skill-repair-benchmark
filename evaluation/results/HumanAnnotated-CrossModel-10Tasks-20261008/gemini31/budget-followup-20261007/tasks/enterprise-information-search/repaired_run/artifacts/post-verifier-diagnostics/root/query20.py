import json

def search():
    with open('/root/DATA/products/PersonalizeForce.json', 'r') as f:
        data = json.load(f)
    
    for m in data.get('meeting_transcripts', []):
        if 'competitor' in str(m).lower() or 'strength' in str(m).lower() or 'weakness' in str(m).lower():
            print(f"MEETING: {m.get('id')}")
            print(json.dumps(m, indent=2))
            print("--------------")
            
search()
