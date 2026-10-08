import json
import os

def search():
    with open('/root/DATA/products/CoachForce.json', 'r') as f:
        data = json.load(f)
        
    for m in data.get('meeting_transcripts', []):
        if m.get('id') == 'CoFoAIX_planning_1':
            print("FOUND MEETING CoFoAIX_planning_1:")
            print(json.dumps(m, indent=2))
            
search()
