import json

answer = {
    "q1": {"answer": ["eid_890654c4", "eid_4555ba9c", "eid_e51b439b", "eid_a1fab288", "eid_c42e5095", "eid_97d7392d", "eid_53a6add1", "eid_9de52b6e", "eid_18571957", "eid_13cb0e90", "eid_737797e3", "eid_8b14b999", "eid_dc8bf84e", "eid_eba4d825"], "tokens": 0},
    "q2": {"answer": ["eid_fce6544f", "eid_d2f0f99a", "eid_5318af37", "eid_a253c65a"], "tokens": 0},
    "q3": {"answer": ["https://personaai.com/demo", "https://smartsuggest.com/demo", "https://tailorai.com/demo"], "tokens": 0}
}

with open('/root/answer.json', 'w') as f:
    json.dump(answer, f, indent=4)
