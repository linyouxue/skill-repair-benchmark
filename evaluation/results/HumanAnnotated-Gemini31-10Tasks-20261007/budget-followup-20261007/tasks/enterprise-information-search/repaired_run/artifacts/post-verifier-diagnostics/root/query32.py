import json

def search():
    with open('/root/DATA/products/CoachForce.json', 'r') as f:
        data = json.load(f)
    
    for m in data.get('meeting_chats', []):
        if 'market research' in str(m).lower() and 'cofoaix' in str(m).lower():
            if m.get('id') == 'CoFoAIX_planning_1_chat':
                print("FOUND CHAT 1")
                print(json.dumps(m, indent=2))
            
search()
