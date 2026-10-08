import json

def get_emp():
    with open('/root/DATA/metadata/employee.json', 'r') as f:
        data = json.load(f)
    print(f"Total employees: {len(data)}")
    names_to_find = ["Ian Jones", "George Jones", "Charlie Smith", "Julia Garcia", "Hannah Miller", "Julia Smith"]
    
    # We saw earlier that the first element was a dict with 'chief_product_officers', 'employee_id' etc. 
    # It might be a deeply nested structure or an org tree. Let's dump all employees flatly.
    def extract_emps(obj, emps):
        if isinstance(obj, dict):
            if 'employee_id' in obj and 'name' in obj:
                emps.append(obj)
            for k, v in obj.items():
                extract_emps(v, emps)
        elif isinstance(obj, list):
            for item in obj:
                extract_emps(item, emps)
                
    emps = []
    extract_emps(data, emps)
    print(f"Flattened employees: {len(emps)}")
    
    for e in emps:
        if e['name'] in names_to_find:
            print(f"Found {e['name']} - ID: {e['employee_id']}")

    print("\nLooking for author eid_890654c4:")
    for e in emps:
        if e['employee_id'] == 'eid_890654c4':
            print(f"Author is {e['name']}")

get_emp()
