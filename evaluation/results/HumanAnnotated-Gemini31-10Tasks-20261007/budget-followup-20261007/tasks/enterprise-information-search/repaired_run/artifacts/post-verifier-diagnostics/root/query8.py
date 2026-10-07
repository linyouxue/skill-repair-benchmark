import json
import os

def search():
    with open('/root/DATA/products/CoachForce.json', 'r') as f:
        data = json.load(f)
        
    for m in data.get('meeting_transcripts', []):
        if m.get('id') in ['CoFoAIX_planning_1', 'CoFoAIX_planning_2', 'CoFoAIX_planning_3', 'CoFoAIX_planning_4', 'CoFoAIX_planning_5']:
            if 'market research' in str(m).lower():
                print(f"MEETING ID: {m.get('id')} has market research")
                print(json.dumps(m, indent=2))
                print("-------------------")
            
search()
