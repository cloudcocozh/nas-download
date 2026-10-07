"""Preserve LinuxServer profile and credentials; enforce private engine API."""
import base64, hashlib, os, re
from pathlib import Path

def configure_engine(root,password,peer_port):
 peer_port=int(peer_port)
 if not 1<=peer_port<=65535 or peer_port in (7120,8080): raise ValueError('invalid peer port')
 directory=Path(root)/'qBittorrent'; directory.mkdir(parents=True,exist_ok=True)
 target=directory/'qBittorrent.conf'; content=target.read_text() if target.exists() else ''
 fresh=not content
 values={'WebUI\\Address':'127.0.0.1','WebUI\\Port':'8080','WebUI\\LocalHostAuth':'true','WebUI\\AuthSubnetWhitelistEnabled':'false','WebUI\\CSRFProtectionEnabled':'true','WebUI\\HostHeaderValidation':'true','Connection\\PortRangeMin':str(peer_port)}
 if fresh:
  if not password: raise ValueError('engine password required')
  salt=os.urandom(16); key=hashlib.pbkdf2_hmac('sha512',password.encode(),salt,100000)
  values.update({'WebUI\\Username':'admin','WebUI\\Password_PBKDF2':'@ByteArray('+base64.b64encode(salt).decode()+':'+base64.b64encode(key).decode()+')','Downloads\\SavePath':'/downloads'})
 def section(name,updates):
  nonlocal content
  pat=r'(?ms)^\['+re.escape(name)+r'\]\s*\n(.*?)(?=^\[|\Z)'; m=re.search(pat,content)
  body=m.group(1) if m else ''
  for k,v in updates.items():
   line=k+'='+v+'\n'; kp=r'(?m)^'+re.escape(k)+r'=.*\n?'
   body=re.sub(kp,lambda _:line,body) if re.search(kp,body) else body.rstrip('\n')+'\n'+line
  replacement='['+name+']\n'+body
  content=content[:m.start()]+replacement+content[m.end():] if m else content.rstrip('\n')+'\n'+replacement
 section('Preferences',values); section('LegalNotice',{'Accepted':'true'})
 section('BitTorrent',{'Session\\Port':str(peer_port)})
 temp=target.with_suffix('.tmp'); temp.write_text(content); os.chmod(temp,0o600); os.replace(temp,target)
 return target

if __name__=='__main__': configure_engine('/config',os.environ['ND_ENGINE_PASSWORD'],os.environ.get('ND_PEER_PORT','7121'))
