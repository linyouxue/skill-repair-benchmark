import json

def search():
    with open('/root/DATA/products/PersonalizeForce.json', 'r') as f:
        data = json.load(f)
    
    for m in data.get('slack', []):
        if m.get('id') in ['20260902-0-ba911', '20260820-10-b2525', '20260810-0-bb012', '20260922-0-0ed21']:
            print(f"SLACK ID: {m.get('id')}, user: {m.get('Message', {}).get('User', {}).get('userId')}")
            
search()
