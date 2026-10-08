import json
import re

def search_coachforce():
    with open('/root/DATA/products/CoachForce.json', 'r') as f:
        data = json.load(f)
    print(f"Loaded CoachForce.json, keys: {data.keys()}")
    
    # Check what kind of data it is
    if isinstance(data, dict):
        for key in data:
            print(f"Key: {key}, type: {type(data[key])}")
            if isinstance(data[key], list):
                print(f"List length: {len(data[key])}")
    
search_coachforce()
