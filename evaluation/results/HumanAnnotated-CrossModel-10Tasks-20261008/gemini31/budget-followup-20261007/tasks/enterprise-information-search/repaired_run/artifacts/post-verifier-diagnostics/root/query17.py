import json

def search():
    with open('/root/DATA/products/PersonalizeForce.json', 'r') as f:
        data = json.load(f)
    
    for m in data.get('meeting_transcripts', []):
        if 'competitor' in str(m).lower() or 'strength' in str(m).lower() or 'weakness' in str(m).lower():
            print(f"MEETING: {m.get('id')}")
            
    for url in data.get('urls', []):
        if 'demo' in str(url).lower() or 'competitor' in str(url).lower():
            print(f"URL: {url.get('link')}")
            
search()
