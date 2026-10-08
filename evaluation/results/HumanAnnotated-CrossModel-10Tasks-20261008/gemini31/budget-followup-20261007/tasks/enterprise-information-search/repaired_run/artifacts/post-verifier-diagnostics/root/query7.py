import json
import os

def search():
    with open('/root/DATA/products/CoachForce.json', 'r') as f:
        data = json.load(f)
        
    for p in data.get('prs', []):
        if 'market research' in p.get('title', '').lower() or 'cofoaix' in p.get('title', '').lower():
            print(f"PR ID: {p.get('id')}, title: {p.get('title')}, reviewers: {p.get('reviewers')}, author: {p.get('author')}")
            
    print("--------------------")
    for m in data.get('meeting_transcripts', []):
        if 'market research' in str(m).lower() or 'cofoaix' in str(m).lower():
            print(f"MEETING ID: {m.get('id')}, title: {m.get('title')}")
            
    print("--------------------")
    for m in data.get('meeting_chats', []):
        if 'market research' in str(m).lower() or 'cofoaix' in str(m).lower():
            print(f"CHAT ID: {m.get('id')}, title: {m.get('title')}")
            
search()
