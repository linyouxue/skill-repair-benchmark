import json
with open('/root/DATA/metadata/employee.json', 'r') as f:
    data = json.load(f)

for k, v in data.items():
    if k in ['eid_fce6544f', 'eid_d2f0f99a', 'eid_5318af37', 'eid_a253c65a']:
        print(f"{k} -> {v.get('name')}")
