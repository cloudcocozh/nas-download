"""Embedded engine lifecycle; no downloader task replay on recovery."""
import json, subprocess, time
from pathlib import Path

ENGINE_URL='http://127.0.0.1:8080'

def enroll_engine(app,password):
 marker=app.data/'bundled-enrolled'
 with app.lock:
  configs=app.configs()
  if not configs:
   c=dict(id=1,name='内置 qBittorrent',type='qbittorrent',url=ENGINE_URL,username='admin',password=password,default_save_path='/downloads')
   app.db.execute('INSERT INTO downloaders VALUES(?,?)',('1',app.cipher.encrypt(json.dumps(c).encode()).decode()))
   app.db.execute("INSERT OR REPLACE INTO counters VALUES('downloaders',?)",(1,))
  elif marker.exists():
   for c in configs:
    if c.get('type')=='qbittorrent' and c.get('url')=='http://qbittorrent:8080':
     c['url']=ENGINE_URL
     app.db.execute('UPDATE downloaders SET config=? WHERE id=?',(app.cipher.encrypt(json.dumps(c).encode()).decode(),str(c['id'])))
  app.db.commit()
  if not configs and not marker.exists(): app.private_write(marker,b'1\n')

class EngineSupervisor:
 def __init__(self,command,probe,max_restarts=3,backoff=2,spawn=subprocess.Popen,startup_timeout=90):
  self.command,self.probe,self.max_restarts,self.backoff,self.spawn=command,probe,max_restarts,backoff,spawn
  self.process=None; self.restarts=0; self.next_start=0; self.state='starting'; self.ready=False; self.started=False; self.startup_timeout=startup_timeout; self.unready_since=None
 def tick(self):
  if self.state in ('failed','stopped'): return
  if self.process is not None and self.process.poll() is not None:
   self.process=None; self.ready=False
   if self.restarts>=self.max_restarts: self.state='failed'; return
   self.restarts+=1; self.next_start=time.monotonic()+self.backoff*2**(self.restarts-1); self.state='recovering'
  if self.process is None and time.monotonic()>=self.next_start:
   try: self.process=self.spawn(self.command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   except OSError:
    self.restarts+=1; self.next_start=time.monotonic()+self.backoff*2**min(self.restarts,5)
    self.state='failed' if self.restarts>self.max_restarts else 'recovering'; return
  if self.process is not None:
   try: self.ready=bool(self.probe())
   except Exception: self.ready=False
   self.state='ready' if self.ready else 'recovering'
   if self.ready: self.unready_since=None
   elif self.unready_since is None: self.unready_since=time.monotonic()
   if self.unready_since is not None and time.monotonic()-self.unready_since>=self.startup_timeout: self.state='failed'
 def status(self): return dict(mode='embedded',ready=self.ready,state=self.state,restarts=self.restarts,max_restarts=self.max_restarts)
 def stop(self):
  self.ready=False; self.state='stopped'
  if self.process is not None and self.process.poll() is None:
   self.process.terminate()
   try: self.process.wait(timeout=45)
   except subprocess.TimeoutExpired:
    self.process.kill(); self.process.wait(timeout=5)

def make_engine_probe(profile,password,adapter_factory=None):
 """Health belongs to the owned process, independent of editable app entries.

 Read only the username; retain configured password hash untouched. A runtime
 password mismatch is an authentication failure, never permission to reset it.
 """
 import re
 if adapter_factory is None:
  from server.adapters import QBittorrent
  adapter_factory=QBittorrent
 content=Path(profile).read_text(encoding='utf8')
 section=re.search(r'(?ms)^\[Preferences\]\s*\n(.*?)(?=^\[|\Z)',content)
 username=re.search(r'(?m)^WebUI\\Username=(.*)$',section.group(1) if section else '')
 config=dict(type='qbittorrent',url=ENGINE_URL,username=username.group(1).strip() if username else 'admin',password=password)
 def probe():
  adapter_factory(config).connect()
  return True
 return probe

def scheduler_allowed(maintenance_marker,engine_status):
 return not Path(maintenance_marker).exists() and bool(engine_status['ready'])
