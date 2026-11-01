"""Configure only the completed task's verifier-side Maven dependency route."""
import shlex
from urllib.parse import urlsplit


async def configure(sandbox, proxy_url):
    proxy = urlsplit(proxy_url)
    if proxy.scheme != "http" or not proxy.hostname or not proxy.port:
        raise RuntimeError("Verifier Maven requires the explicit HTTP proxy endpoint")
    values = {"id":"benchmark-verifier-proxy", "active":"true", "protocol":"http",
              "host":proxy.hostname, "port":str(proxy.port), "nonProxyHosts":"localhost|127.0.0.1"}
    script = """from pathlib import Path
import xml.etree.ElementTree as E
p=Path('/root/.m2/settings.xml');p.parent.mkdir(parents=True,exist_ok=True)
r=E.parse(p).getroot() if p.exists() else E.Element('settings')
ns=r.tag.split('}')[0]+'}' if '}' in r.tag else ''
proxies=r.find(ns+'proxies')
if proxies is None:proxies=E.SubElement(r,ns+'proxies')
for old in list(proxies):
 protocol=old.find(ns+'protocol')
 if protocol is not None and protocol.text=='http':
  active=old.find(ns+'active')
  if active is None:active=E.SubElement(old,ns+'active')
  active.text='false'
q=E.SubElement(proxies,ns+'proxy')
for k,v in VALUES.items():E.SubElement(q,ns+k).text=v
E.ElementTree(r).write(p,encoding='utf-8',xml_declaration=True)
""".replace("VALUES",repr(values))
    result = await sandbox.exec("python3 -c "+shlex.quote(script),user="root",timeout_sec=10)
    if result.return_code:
        raise RuntimeError("Could not configure the verifier-only Maven proxy")
    return {"settings_path":"/root/.m2/settings.xml", "host":proxy.hostname, "port":proxy.port,
            "scope":"verifier-after-generation", "documentation":"https://maven.apache.org/guides/mini/guide-proxies.html"}
