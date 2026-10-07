import json

def search():
    with open('/root/DATA/products/CoachForce.json', 'r') as f:
        data = json.load(f)
    
    for m in data.get('meeting_transcripts', []):
        if 'market research' in str(m).lower() and 'cofoaix' in str(m).lower():
            if m.get('id') == 'CoFoAIX_planning_1':
                # Already printed this one
                pass
            else:
                print(f"MEETING ID: {m.get('id')}")
            
search()
