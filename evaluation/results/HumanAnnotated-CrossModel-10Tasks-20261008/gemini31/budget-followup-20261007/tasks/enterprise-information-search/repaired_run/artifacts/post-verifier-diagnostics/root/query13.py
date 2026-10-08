import json

def search():
    with open('/root/DATA/products/PersonalizeForce.json', 'r') as f:
        data = json.load(f)
    print("Loaded PersonalizeForce.json")
    
    docs = data['documents']
    for doc in docs:
        if 'competitor' in str(doc).lower() or 'strength' in str(doc).lower() or 'weakness' in str(doc).lower():
            print(f"DOC: {doc.get('id')}")
            #print(json.dumps(doc, indent=2))
            
    # prs
    for pr in data.get('prs', []):
        if 'competitor' in str(pr).lower():
            print(f"PR: {pr.get('id')}")
            
    # meetings
    for m in data.get('meeting_transcripts', []):
        if 'competitor' in str(m).lower() or 'strength' in str(m).lower():
            print(f"MEETING: {m.get('id')}")
            
    for m in data.get('meeting_chats', []):
        if 'competitor' in str(m).lower() or 'strength' in str(m).lower():
            print(f"CHAT: {m.get('id')}")
            
    for url in data.get('urls', []):
        if 'demo' in str(url).lower() or 'competitor' in str(url).lower():
            print(f"URL: {url}")
            
search()
