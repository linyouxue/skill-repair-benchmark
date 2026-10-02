import importlib.util,json,math
from statistics import NormalDist
spec=importlib.util.spec_from_file_location("revised","/tmp/rar-consistency-r002/test_outputs.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
real=m.cell_value
results={}
for z in [NormalDist().inv_cdf(.95),1.64,1.645,1.65]:
    def changed(ws,c,z=z):
        if c=="C3":return z
        v=real(ws,c)
        if c in [f"{col}13" for col in m.STEP2_COLS]+[f"{col}24" for col in m.STEP3_COLS]:return v*z/1.645
        return v
    m.cell_value=changed
    m.test_step1_volatility_calculations();m.test_step2_gold_reserves_and_risk();m.test_step3_rar_percentage()
    results[str(z)]="accept consistent valid confidence"
for name,z,factor in [("wrong_one_sided_z",1.96,1),("original_extra_sqrt3",1.645,math.sqrt(3))]:
    def changed(ws,c,z=z,factor=factor):
        if c=="C3":return z
        v=real(ws,c)
        if c in [f"{col}13" for col in m.STEP2_COLS]+[f"{col}24" for col in m.STEP3_COLS]:return v*factor
        return v
    m.cell_value=changed
    for fn in [m.test_step2_gold_reserves_and_risk,m.test_step3_rar_percentage]:
        try:fn()
        except AssertionError:results[name+":"+fn.__name__]="rejected"
        else:raise AssertionError("negative control incorrectly accepted")
m.cell_value=real
print(json.dumps(results,indent=2))
