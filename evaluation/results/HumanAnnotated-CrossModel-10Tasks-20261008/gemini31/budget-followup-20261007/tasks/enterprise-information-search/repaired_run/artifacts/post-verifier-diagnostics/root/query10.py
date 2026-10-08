import json

def get_employee_eids():
    with open('/root/DATA/metadata/employee.json', 'r') as f:
        data = json.load(f)
    print(f"Total employees: {len(data)}")
    
    # search names
    for emp in data:
        name = emp.get('name')
        if name in ["Ian Jones", "George Jones", "Hannah Miller", "George Miller", "Charlie Smith", "Julia Garcia", "Julia Davis"]:
            print(f"Found: {name} -> {emp.get('id')}")
            
get_employee_eids()
