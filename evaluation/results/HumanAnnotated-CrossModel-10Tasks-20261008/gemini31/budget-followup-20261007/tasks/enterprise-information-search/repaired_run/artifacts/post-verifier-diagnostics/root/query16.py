import json

def search():
    with open('/root/DATA/products/PersonalizeForce.json', 'r') as f:
        data = json.load(f)
    
    meetings = data.get('meeting_transcripts', [])
    for m in meetings:
        if 'competitor' in str(m).lower() or 'strength' in str(m).lower() or 'weakness' in str(m).lower():
            if m.get('id') in ['OnalizeAIX_planning_1', 'OnalizeAIX_planning_2', 'OnalizeAIX_planning_3', 'OnalizeAIX_planning_4', 'OnalizeAIX_planning_5']:
                print(f"MEETING: {m.get('id')}")
                print(json.dumps(m, indent=2))
                print("-------------------")
            
search()
