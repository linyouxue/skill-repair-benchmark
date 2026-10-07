import json
def match():
    with open('/root/DATA/metadata/employee.json', 'r') as f:
        data = json.load(f)
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
    
    # Let's cross reference with participants of CoFoAIX_planning_1 which was:
    # ['eid_99835861', 'eid_50da4819', 'eid_ee9ca887', 'eid_8df92d08', 'eid_85a4de81', 'eid_965867b8', 'eid_59bbe6f6']
    participants = ['eid_99835861', 'eid_50da4819', 'eid_ee9ca887', 'eid_8df92d08', 'eid_85a4de81', 'eid_965867b8', 'eid_59bbe6f6', 'eid_890654c4']
    for p in participants:
        for e in emps:
            if e['employee_id'] == p:
                print(f"{p}: {e['name']}")
                
match()
