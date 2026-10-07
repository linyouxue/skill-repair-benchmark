import json

with open('/root/DATA/metadata/employee.json', 'r') as f:
    data = json.load(f)
    print(type(data))
    if isinstance(data, dict):
        print(list(data.keys())[:5])
        for k,v in list(data.items())[:3]:
            print(f"{k}: {v}")
    elif isinstance(data, list):
        print(data[:3])
        print(type(data[0]))
