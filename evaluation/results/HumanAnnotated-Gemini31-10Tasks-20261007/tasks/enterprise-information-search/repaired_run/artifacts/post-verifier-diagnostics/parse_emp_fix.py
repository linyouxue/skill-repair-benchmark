import json

def get_emp():
    with open('/root/DATA/metadata/employee.json', 'r') as f:
        data = json.load(f)
    print(f"Total employees: {len(data)}")
    names_to_find = ["Ian Jones", "George Jones", "Charlie Smith", "Julia Garcia", "Hannah Miller", "Julia Smith"]
    for e in data:
        if e['name'] in names_to_find:
            print(f"Found {e['name']} - ID: {e['employee_id']}")

    print("\nLooking for author eid_890654c4:")
    for e in data:
        if e['employee_id'] == 'eid_890654c4':
            print(f"Author is {e['name']}")
get_emp()
