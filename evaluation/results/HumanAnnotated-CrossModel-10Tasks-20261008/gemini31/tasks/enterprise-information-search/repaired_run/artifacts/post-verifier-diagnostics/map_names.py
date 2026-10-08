import json

def get_eids(names):
    with open('/root/DATA/metadata/employee.json', 'r') as f:
        data = json.load(f)
    eids = []
    for name in names:
        found = False
        for emp in data:
            if isinstance(emp, dict) and 'name' in emp and emp['name'].lower() == name.lower():
                eids.append(emp['employee_id'])
                found = True
                break
            elif isinstance(emp, list) and len(emp) > 2 and str(emp[1]).lower() == name.lower():
                # Just in case it's a list
                eids.append(emp[0])
                found = True
                break
        if not found:
            eids.append(None)
    return eids

names = ["Ian Jones", "George Jones", "Charlie Smith", "Julia Garcia", "Hannah Miller", "Julia Smith"]
eids = get_eids(names)
for n, e in zip(names, eids):
    print(f"{n}: {e}")
