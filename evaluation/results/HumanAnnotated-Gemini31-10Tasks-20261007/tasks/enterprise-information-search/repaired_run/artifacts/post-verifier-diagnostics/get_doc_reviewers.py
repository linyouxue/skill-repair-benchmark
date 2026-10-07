import json

def get_reviewers():
    with open('/root/DATA/products/CoachForce.json', 'r') as f:
        data = json.load(f)
        
    for doc in data.get('documents', []):
        if doc.get('id') == 'latest_cofoaix_market_research_report':
            print(f"Doc ID: {doc.get('id')} - Date: {doc.get('date')} - Author: {doc.get('author')}")
            for k, v in doc.items():
                if 'review' in k.lower():
                    print(f"  {k}: {v}")
            # Also check if it's the right product. The question asks for "Market Research Report for the CoachForce product". 
            # The one I found says "cofoaix", maybe "SalesCoach"? Let's print out all doc types.
            
    print("\nLet's find Market Research Report for CoachForce:")
    for doc in data.get('documents', []):
        t = doc.get('type', '').lower()
        if 'market' in t or 'research' in t:
            print(f"Doc ID: {doc.get('id')} - Type: {doc.get('type')} - Author: {doc.get('author')}")
            
    # Maybe check meeting transcripts for SalesCoach?
    for m in data.get('meeting_transcripts', []):
        t = m.get('document_type', '').lower()
        if 'market' in t or 'research' in t:
            print(f"Meeting ID: {m.get('id')} - Type: {m.get('document_type')}")
            print(f"  Participants: {m.get('participants')}")

get_reviewers()
