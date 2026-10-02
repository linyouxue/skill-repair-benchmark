import importlib.util,json,copy
spec=importlib.util.spec_from_file_location('revised','/tmp/azure-origin-validation-v1/test_outputs.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
d=json.load(open('/app/output/oscillation_report.json'))
tester=m.TestSolutionEvaluation()
def check(x):
    m.TestDetection().test_output_structure(x)
    m.TestDetection().test_oscillation_detected(x)
    m.TestDetection().test_route_leak_detected(x)
    for n,a,b in tester.SOLUTION_EXPECTATIONS:tester.test_solution_classification(x,n,a,b)
check(d)
records=[]
for token,field,value in [('RPKI','route_leak_resolved',True),('block announcing provider','oscillation_resolved',True),('bgp community','oscillation_resolved',True)]:
    x=copy.deepcopy(d);key=next(k for k in x['solution_results'] if token in k)
    x['solution_results'][key][field]=value
    try:check(x)
    except AssertionError:records.append({'mutation':token+' '+field,'rejected':True})
    else:raise AssertionError('negative control incorrectly accepted')
print(json.dumps({'actual_source_passed':True,'negative_controls':records}))
