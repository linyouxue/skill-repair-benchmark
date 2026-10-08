import json

def search():
    with open('/root/DATA/products/CoachForce.json', 'r') as f:
        data = json.load(f)
    
    docs = data['documents']
    for doc in docs:
        if 'market' in str(doc).lower():
            if 'market research report' in str(doc).lower() and doc.get('type') == 'Market Research Report':
                if 'coachforce' in doc.get('id', '').lower() or 'coachforce' in doc.get('title', '').lower() or 'coachforce' in doc.get('content', '').lower() or 'coachforce' in doc.get('document_link', '').lower():
                    print("FOUND COACHFORCE MARKET RESEARCH REPORT:")
                    print(json.dumps(doc, indent=2))
            
    # Now look at prs
    prs = data.get('prs', [])
    for pr in prs:
        #print(pr.keys())
        #break
        if 'market research' in str(pr).lower() and ('coachforce' in str(pr).lower() or 'cofoaix' in str(pr).lower()):
            print(f"PR: {pr.get('id')}, {pr.get('title')}, {pr.get('author')}, reviewers: {pr.get('reviewers')}")

search()
