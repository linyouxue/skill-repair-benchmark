"""Read-only same-artifact browser probe of exact official hover helper and selector.
No task, verifier, CSS/JS, output or reward changes; diagnostic only.
"""
import json,hashlib,subprocess,os
from pathlib import Path
L=Path(__file__).parent;S=L/'audit-evidence';id='location-data-to-d3';attempt='attempt-006';j=next((L/'new-attempts/repaired'/id/attempt).glob('jobs/*/task__*'));tr=j/'trajectory/acp_trajectory.jsonl';h=hashlib.sha256(tr.read_bytes()).hexdigest();snap=next((p for p in (S/'rerun_artifacts'/id/attempt).rglob('SNAPSHOT.json') if json.loads(p.read_text()).get('acp_sha256_at_collection')==h),None);assert snap;d=json.loads(snap.read_text());root=Path(next(x['destination'] for x in d['artifacts'] if x['source_path']=='/root/output' and x['copy_exit']==0));verifier=L.parents[1]/'prepared_revisions/task-dependencies-v4/repaired'/id/'task/verifier/test_outputs.py';code=r'''
import json,ast,threading,functools,http.server
from pathlib import Path
from playwright.sync_api import sync_playwright
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
srv=http.server.ThreadingHTTPServer(('127.0.0.1',8765),functools.partial(Quiet,directory='/root/output'));threading.Thread(target=srv.serve_forever,daemon=True).start()
tree=ast.parse(Path('/verifier/test_outputs.py').read_text());test=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='test_tooltips_non_etf_and_etf');helpers=[x for x in test.body if isinstance(x,ast.FunctionDef) and x.name in ['hover_label_text','find_first_non_etf_label']]
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True);page=browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto('http://127.0.0.1:8765/index.html',wait_until='networkidle');page.wait_for_timeout(3500)
 ns={'page':page,'svg_texts':page.locator('svg text'),'etf_tickers':['SPY','VOO','QQQ','GLD','XLF','VWO','XLU','XLV','VEA','VTV']};exec(compile(ast.Module(body=helpers,type_ignores=[]),'<exact official nested helpers>','exec'),ns)
 label=ns['find_first_non_etf_label']();page.mouse.move(0,0);page.wait_for_timeout(500);hovered=ns['hover_label_text'](label)
 def actual():return page.locator('#tooltip').evaluate('(el)=>({opacity:getComputedStyle(el).opacity,visibility:getComputedStyle(el).visibility,display:getComputedStyle(el).display,text:el.innerText,className:el.className,rect:{width:el.getBoundingClientRect().width,height:el.getBoundingClientRect().height}})')
 non=actual();locator='.tooltip.visible, #tooltip.visible, [role="tooltip"][class*="visible"]';official=page.locator(locator).count();page.mouse.move(0,0);page.wait_for_timeout(500);eh=ns['hover_label_text']('SPY');etf=actual();print(json.dumps({'diagnostic_only_no_score_change':True,'non_etf_label':label,'exact_official_hover_helper_succeeded':hovered,'non_etf_tooltip_actual_style_and_text':non,'official_selector_count_after_non_etf_hover':official,'etf_hover_succeeded':eh,'etf_tooltip_actual_style_after_reset_and_hover':etf,'page_errors':errors,'browser_version':browser.version},ensure_ascii=False));browser.close()
srv.shutdown()
''';env=os.environ.copy();env.update(DOCKER_HOST='unix:///Users/king/.docker/run/docker.sock',DOCKER_CONFIG=str(L.parents[1]/'docker-config'));env.pop('DOCKER_CONTEXT',None);cmd=['docker','run','--rm','-i','--network','none','--cpus','2','--memory','4294967296','--memory-swap','8589934592','-v',str(root)+':/root/output:ro','-v',str(verifier)+':/verifier/test_outputs.py:ro','--entrypoint','/opt/skilltta-verifier-v2/bin/python',d['image_id'],'-'];q=subprocess.run(cmd,input=code,env=env,capture_output=True,text=True,timeout=90);out={'id':id,'attempt':attempt,'diagnostic_only_no_score_change':True,'command':cmd,'probe_source':code,'probe_source_sha256':hashlib.sha256(code.encode()).hexdigest(),'actual_image_id':d['image_id'],'verifier_source_sha256':hashlib.sha256(verifier.read_bytes()).hexdigest(),'actual_js_sha256':hashlib.sha256((root/'js/visualization.js').read_bytes()).hexdigest(),'actual_css_sha256':hashlib.sha256((root/'css/style.css').read_bytes()).hexdigest(),'exit_code':q.returncode,'stdout':q.stdout,'stderr':q.stderr,'source_snapshot':str(snap),'acp_sha256':h};
try:out['parsed_result']=json.loads(q.stdout)
except:pass
p=S/'d3_tooltip_visible_class_probe_actual_verifier_python.json';p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print('D3 diagnostic probe exit',q.returncode,'result',out.get('parsed_result'),'stderr',q.stderr[:500])
