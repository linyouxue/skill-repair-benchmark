import json

with open('/root/DATA/metadata/employee.json', 'r') as f:
    data = json.load(f)
    print("Employee structure check:")
    for emp in data:
        if isinstance(emp, dict):
            print(f"emp keys: {emp.keys()}")
            print(f"emp first val: {emp}")
            break
        elif isinstance(emp, list):
            print(f"emp list len: {len(emp)}")
            print(f"emp: {emp}")
            break
            
print("\nNow let's check salesforce_team.json")
with open('/root/DATA/metadata/salesforce_team.json', 'r') as f:
    sf_data = json.load(f)
    print(type(sf_data))
    if isinstance(sf_data, dict):
        for k in list(sf_data.keys())[:3]:
            print(k)
    elif isinstance(sf_data, list):
        print(f"List len {len(sf_data)}")
        if len(sf_data) > 0:
            print(sf_data[0])
            
print("\nLet's check customers_data.json")
with open('/root/DATA/metadata/customers_data.json', 'r') as f:
    sf_data = json.load(f)
    print(type(sf_data))
    if isinstance(sf_data, list) and len(sf_data) > 0:
        print(sf_data[0])
