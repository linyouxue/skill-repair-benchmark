import json

def get_employee_eids():
    with open('/root/DATA/metadata/employee.json', 'r') as f:
        data = json.load(f)
    print(f"Type: {type(data)}")
    if isinstance(data, dict):
        for k, v in data.items():
            if v.get('name') in ["Ian Jones", "George Jones", "Hannah Miller", "George Miller", "Charlie Smith", "Julia Garcia", "Julia Davis", "Julia Smith"]:
                print(f"Found: {v.get('name')} -> {v.get('id')}")
            
get_employee_eids()
