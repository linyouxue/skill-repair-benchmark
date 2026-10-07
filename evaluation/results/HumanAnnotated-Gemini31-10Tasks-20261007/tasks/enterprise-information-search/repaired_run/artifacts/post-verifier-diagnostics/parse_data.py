import json

def explore_json(path):
    with open(path, 'r') as f:
        data = json.load(f)
    if isinstance(data, dict):
        print(f"Keys: {data.keys()}")
        if 'artifacts' in data:
            print(f"Number of artifacts: {len(data['artifacts'])}")
            if len(data['artifacts']) > 0:
                print(f"First artifact keys: {data['artifacts'][0].keys()}")
                print(f"First artifact type: {data['artifacts'][0].get('type')}")
        else:
            print("No artifacts key")
            for k, v in list(data.items())[:3]:
                print(f"Key {k} type: {type(v)}")
                if isinstance(v, list) and len(v) > 0:
                    print(f"  First item keys: {v[0].keys()}")
    elif isinstance(data, list):
        print(f"List of length {len(data)}")
        if len(data) > 0:
            print(f"First item keys: {data[0].keys()}")

print("CoachForce.json:")
explore_json('/root/DATA/products/CoachForce.json')
print("\nPersonalizeForce.json:")
explore_json('/root/DATA/products/PersonalizeForce.json')
