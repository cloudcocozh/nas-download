"""Standalone authenticated NAS downloader API. Secrets never leave the store."""
import base64, hashlib, hmac, ipaddress, json, mimetypes, os, re, secrets, socket, sqlite3, threading, time, uuid
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from urllib.parse import urlsplit, parse_qs, unquote
from cryptography.fernet import Fernet
from . import VERSION

class ApiError(Exception):
    def __init__(self, code, message, status=400): self.code,self.message,self.status=code,message,status

def validate_url(value,allow_query=False):
    if not isinstance(value,str) or len(value)>2048 or any(ord(c)<32 for c in value): raise ApiError('INVALID_URL','下载器地址无效')
    try:
        p=urlsplit(value); port=p.port
        if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or p.fragment or (p.query and not allow_query): raise ValueError()
        addresses=socket.getaddrinfo(p.hostname,port or (443 if p.scheme=='https' else 80),type=socket.SOCK_STREAM)
        for a in addresses:
            ip=ipaddress.ip_address(a[4][0])
            if getattr(ip,'ipv4_mapped',None): ip=ip.ipv4_mapped
            if ip.is_link_local or ip.is_multicast or ip.is_unspecified or str(ip)=='100.100.100.200': raise ValueError()
    except (ValueError,OSError): raise ApiError('INVALID_URL','下载器地址无效或指向禁止的元数据地址')
    return value.rstrip('/')

def digest(token): return hashlib.sha256(token.encode()).hexdigest()
def canonical_uuid(rid):
    try:
        normalized=str(uuid.UUID(rid))
        if normalized!=rid.lower(): raise ValueError()
        return normalized
    except (ValueError,TypeError,AttributeError): raise ApiError('INVALID_REQUEST_ID','request_id 必须是 UUID')
def operation_fingerprint(payload):
    clean={k:v for k,v in payload.items() if k!='request_id'}
    return digest(json.dumps(clean,sort_keys=True,separators=(',',':')))
def password_hash(password,salt): return hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
def text(data,key,default=None,maximum=1024):
    value=data.get(key,default)
    if not isinstance(value,str) or len(value)>maximum: raise ApiError('INVALID_INPUT',key+' 必须是有效文本')
    return value
def boolean(data,key,default=False):
    value=data.get(key,default)
    if type(value) is not bool: raise ApiError('INVALID_INPUT',key+' 必须为布尔值')
    return value

class Application:
    def __init__(self,data,setup_token=None):
        self.data=Path(data); self.data.mkdir(parents=True,exist_ok=True); self.lock=threading.RLock(); self.rates={}
        self.snapshot_lock=threading.RLock(); self.snapshots={}
        keyfile=self.data/'secret.key'
        if not keyfile.exists(): self.private_write(keyfile,Fernet.generate_key())
        self.cipher=Fernet(keyfile.read_bytes())
        self.db=sqlite3.connect(self.data/'nas-download.sqlite3',check_same_thread=False); self.db.row_factory=sqlite3.Row
        self.db.executescript('''PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY,salt TEXT,hash TEXT);
        CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,hash TEXT UNIQUE,label TEXT,created_at REAL,last_seen REAL,expires_at REAL);
        CREATE TABLE IF NOT EXISTS pairs(hash TEXT PRIMARY KEY,label TEXT,expires_at REAL);
        CREATE TABLE IF NOT EXISTS downloaders(id TEXT PRIMARY KEY,config TEXT);
        CREATE TABLE IF NOT EXISTS operations(id TEXT PRIMARY KEY,fingerprint TEXT,receipt TEXT,created_at REAL);
        CREATE TABLE IF NOT EXISTS counters(name TEXT PRIMARY KEY,value INTEGER);
        '''); self.db.commit()
        os.chmod(self.data/'nas-download.sqlite3',0o600)
        setupfile=self.data/'setup-token'
        self.generated_setup=False
        if setup_token: self.setup_token=setup_token
        elif setupfile.exists(): self.setup_token=setupfile.read_text().strip()
        else:
            self.setup_token=secrets.token_urlsafe(24); self.private_write(setupfile,self.setup_token.encode()); self.generated_setup=True
        from .sites import SiteService
        self.sites=SiteService(self)
        from .automations import AutomationService
        self.automations=AutomationService(self)
    @staticmethod
    def private_write(path,data):
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as f: f.write(data)
    def configured(self):
        with self.lock: return bool(self.db.execute('SELECT 1 FROM users').fetchone())
    def issue(self,label):
        token=secrets.token_urlsafe(32); now=time.time(); sid=str(uuid.uuid4())
        self.db.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?)',(sid,digest(token),label,now,now,now+30*86400)); self.db.commit()
        return {'ok':True,'token':token,'username':self.db.execute('SELECT username FROM users').fetchone()[0]}
    def authenticate(self,token):
        with self.lock:
            row=self.db.execute('SELECT * FROM sessions WHERE hash=? AND expires_at>?',(digest(token),time.time())).fetchone()
            if not row: raise ApiError('UNAUTHORIZED','请先登录',401)
            self.db.execute('UPDATE sessions SET last_seen=? WHERE id=?',(time.time(),row['id'])); self.db.commit(); return dict(row)
    def throttle(self,ip,route):
        with self.lock:
            now=time.time(); key=(ip,route); hits=[t for t in self.rates.get(key,[]) if now-t<60]
            if len(hits)>=10: raise ApiError('RATE_LIMIT','尝试过于频繁，请稍后再试',429)
            self.rates[key]=hits+[now]
            if len(self.rates)>4096: self.rates={k:v for k,v in self.rates.items() if v and now-v[-1]<60}
    def configs(self):
        with self.lock: return [json.loads(self.cipher.decrypt(r[0].encode())) for r in self.db.execute('SELECT config FROM downloaders')]
    def config(self,did):
        for c in self.configs():
            if str(c['id'])==str(did): return c
        raise ApiError('NOT_FOUND','下载器不存在',404)
    @staticmethod
    def public(c): return {k:c[k] for k in ('id','name','type','url','default_save_path','version') if k in c}
    def adapter(self,c):
        if getattr(self,"stopping",False) or (self.data/".install-maintenance").exists(): raise ApiError("MAINTENANCE","Service maintenance",503)
        if c.get("url")=="http://127.0.0.1:8080" and hasattr(self,"engine_status") and not self.engine_status()["ready"]: raise ApiError("ENGINE_UNAVAILABLE","Engine recovering",503)
        from .adapters import QBittorrent,Transmission
        return (QBittorrent if c['type']=='qbittorrent' else Transmission)(c)
    def task_snapshot(self,c):
        # Single-flight fetch prevents concurrent page requests creating new logins.
        with self.snapshot_lock:
            key=str(c['id']); cached=self.snapshots.get(key)
            if cached and time.monotonic()-cached[0]<2: return cached[1]
            items=self.adapter(c).tasks()
            if key not in self.snapshots and len(self.snapshots)>=128:
                oldest=min(self.snapshots,key=lambda k:self.snapshots[k][0]); del self.snapshots[oldest]
            self.snapshots[key]=(time.monotonic(),items); return items
    def invalidate_snapshot(self,did):
        with self.snapshot_lock: self.snapshots.pop(str(did),None)
    def mutate(self,did,fn):
        if getattr(self,"stopping",False) or (self.data/".install-maintenance").exists(): raise ApiError("MAINTENANCE","Service maintenance",503)
        try: return fn()
        finally: self.invalidate_snapshot(did)
    def existing_operation(self,rid,payload):
        rid=canonical_uuid(rid); fp=operation_fingerprint(payload)
        with self.lock:
            existing=self.db.execute('SELECT * FROM operations WHERE id=?',(rid,)).fetchone()
            if existing:
                if existing['fingerprint']!=fp: raise ApiError('REQUEST_ID_CONFLICT','同一请求编号不能用于不同操作',409)
                return json.loads(existing['receipt'])
        return None
    def operation(self,rid,payload,fn):
        rid=canonical_uuid(rid)
        with self.lock:
            existing=self.existing_operation(rid,payload)
            if existing: return existing
            fp=operation_fingerprint(payload)
            receipt={'request_id':rid,'status':'uncertain','message':'请求已登记；结果尚未确认，禁止重复提交','created_at':time.time()}
            self.db.execute('INSERT INTO operations VALUES(?,?,?,?)',(rid,fp,json.dumps(receipt),time.time())); self.db.commit()
        try:
            fn(); receipt.update(status='completed',message='下载器已接受操作')
        except Exception: receipt.update(message='下载器未能确认结果；请查看任务状态，勿重新提交该请求')
        with self.lock:
            self.db.execute('UPDATE operations SET receipt=? WHERE id=?',(json.dumps(receipt),rid)); self.db.commit()
        return receipt
    def dispatch(self,method,path,q,b,session,ip):
        if path=='/health' and method=='GET':
            engine=self.engine_status() if hasattr(self,'engine_status') else {'mode':'existing','ready':True,'state':'external'}
            return {'ok':engine['ready'] and not getattr(self,'stopping',False),'version':VERSION,'configured':self.configured(),'name':'Nas Download','engine':engine,'maintenance':(self.data/'.install-maintenance').exists()}
        if getattr(self,'stopping',False) or (self.data/'.install-maintenance').exists(): raise ApiError('MAINTENANCE','Service maintenance',503)
        if path in ('/setup','/login','/pair') and method=='POST':
            self.throttle(ip,path)
            with self.lock:
                if path=='/setup':
                    if self.configured(): raise ApiError('ALREADY_CONFIGURED','服务已初始化',409)
                    if not hmac.compare_digest(text(b,'setup_token'),self.setup_token): raise ApiError('INVALID_SETUP_TOKEN','初始化码错误',401)
                    username=text(b,'username',maximum=100).strip(); pw=text(b,'password',maximum=1024)
                    if not username or len(pw)<10: raise ApiError('WEAK_CREDENTIALS','用户名不能为空，密码至少 10 个字符')
                    salt=secrets.token_hex(16); self.db.execute('INSERT INTO users VALUES(?,?,?)',(username,salt,password_hash(pw,salt))); self.db.commit()
                    tokenfile=self.data/'setup-token'
                    if tokenfile.exists(): tokenfile.unlink()
                    return self.issue(text(b,'label','浏览器',100))
                if path=='/login':
                    row=self.db.execute('SELECT * FROM users WHERE username=?',(text(b,'username',maximum=100),)).fetchone(); pw=text(b,'password')
                    salt=row['salt'] if row else '00'*16; actual=password_hash(pw,salt)
                    if not row or not hmac.compare_digest(actual,row['hash']): raise ApiError('INVALID_CREDENTIALS','账号或密码错误',401)
                    return self.issue(text(b,'label','浏览器',100))
                code=text(b,'code',maximum=8)
                row=self.db.execute('SELECT * FROM pairs WHERE hash=? AND expires_at>?',(digest(code),time.time())).fetchone()
                if not row: raise ApiError('INVALID_PAIR_CODE','配对码无效或已过期',401)
                self.db.execute('DELETE FROM pairs WHERE hash=?',(digest(code),)); self.db.commit(); return self.issue(text(b,'label',row['label'],100))
        if not session: raise ApiError('UNAUTHORIZED','请先登录',401)
        if path=='/automations' or path.startswith('/automations/') or path.startswith('/automation-runs/'):
            return self.automations.dispatch(method,path,q,b)
        if path=='/sites' or path.startswith('/sites/') or path=='/searches' or path.startswith('/searches/'):
            return self.sites.dispatch(method,path,q,b,session)
        if path=='/me' and method=='GET': return {'ok':True,'username':self.db.execute('SELECT username FROM users').fetchone()[0],'version':VERSION}
        if path=='/logout' and method=='POST':
            with self.lock: self.db.execute('DELETE FROM sessions WHERE id=?',(session['id'],)); self.db.commit()
            return {'ok':True}
        if path=='/pair-codes' and method=='POST':
            code='%08d'%secrets.randbelow(100000000); expiry=time.time()+300
            with self.lock:
                self.db.execute('DELETE FROM pairs WHERE expires_at<?',(time.time(),)); self.db.execute('INSERT INTO pairs VALUES(?,?,?)',(digest(code),text(b,'label','手机',100),expiry)); self.db.commit()
            return {'ok':True,'code':code,'expires_at':expiry}
        if path=='/devices' and method=='GET':
            with self.lock: items=[{k:r[k] for k in ('id','label','created_at','last_seen')}|{'current':r['id']==session['id']} for r in self.db.execute('SELECT * FROM sessions WHERE expires_at>?',(time.time(),))]
            return {'ok':True,'items':items}
        if path.startswith('/devices/') and method=='DELETE':
            with self.lock: self.db.execute('DELETE FROM sessions WHERE id=?',(path.split('/')[-1],)); self.db.commit()
            return {'ok':True}
        if path=='/downloaders' and method=='GET': return {'ok':True,'items':[self.public(c) for c in self.configs()]}
        if (path in ('/downloaders','/downloaders/test') and method=='POST') or (path.startswith('/downloaders/') and method=='PATCH'):
            old=self.config(path.split('/')[-1]) if method=='PATCH' else self.config(b['downloader_id']) if path=='/downloaders/test' and 'downloader_id' in b else {}
            c=old|b; c={k:text(c,k,default,maximum) for k,default,maximum in [('name','下载器',100),('type',None,32),('url',None,2048),('username','',1024),('password','',1024),('default_save_path','',4096)]}
            if old and not c['password']: c['password']=old.get('password','')
            if c['type'] not in ('qbittorrent','transmission'): raise ApiError('UNSUPPORTED_DOWNLOADER','仅支持 qBittorrent 4/5 和 Transmission 4')
            c['url']=validate_url(c['url']); c['version']=self.adapter(c).connect()
            if path=='/downloaders/test': return {'ok':True,'version':c['version']}
            with self.lock:
                if old: c['id']=old['id']
                else:
                    counter=self.db.execute("SELECT value FROM counters WHERE name='downloaders'").fetchone()
                    c['id']=max(counter[0] if counter else 0,max([int(x['id']) for x in self.configs() if str(x['id']).isdigit()]+[0]))+1
                    self.db.execute("INSERT OR REPLACE INTO counters VALUES('downloaders',?)",(c['id'],))
                self.db.execute('INSERT OR REPLACE INTO downloaders VALUES(?,?)',(c['id'],self.cipher.encrypt(json.dumps(c).encode()).decode())); self.db.commit()
            self.invalidate_snapshot(c['id'])
            return {'ok':True,'item':self.public(c)}
        if path.startswith('/downloaders/') and method=='DELETE':
            self.config(path.split('/')[-1])
            with self.lock: self.db.execute('DELETE FROM downloaders WHERE id=?',(path.split('/')[-1],)); self.db.commit()
            self.invalidate_snapshot(path.split('/')[-1])
            return {'ok':True}
        if path=='/tasks' and method=='GET':
            did=q.get('downloader_id','all'); selected=self.configs() if did=='all' else [self.config(did)]; items=[]; errors=[]
            for c in selected:
                try: items.extend(self.task_snapshot(c))
                except ApiError as e:
                    if did!='all': raise
                    errors.append({'downloader_id':c['id'],'error':e.message})
            state=q.get('state','all')
            if state not in ('all','downloading','completed','paused'): raise ApiError('INVALID_STATE','任务状态无效')
            summary={'download_speed':sum(i['download_speed'] for i in items),'upload_speed':sum(i['upload_speed'] for i in items),'total':len(items)}
            summary.update({s:sum(i['state']==s for i in items) for s in ('downloading','completed','paused')})
            items=[i for i in items if (state=='all' or i['state']==state) and q.get('query','').casefold() in i['name'].casefold()]
            offset=integer(q,'offset',0,0,1000000); limit=integer(q,'limit',50,1,200)
            return {'ok':True,'items':items[offset:offset+limit],'total':len(items),'summary':summary,'errors':errors}
        if path=='/tasks/add' and method=='POST':
            existing=self.existing_operation(text(b,'request_id'),b)
            if existing: return {'ok':True,'operation':existing}
            did=b.get('downloader_id')
            if not isinstance(did,(str,int)) or isinstance(did,bool): raise ApiError('INVALID_INPUT','downloader_id 无效')
            c=self.config(did); payload=dict(b); boolean(b,'paused'); url=text(b,'url','',4096); torrent=text(b,'torrent_base64','',3000000)
            if bool(url)==bool(torrent): raise ApiError('INVALID_TORRENT','请选择磁力/种子链接或种子文件其中一种')
            if url and not (url.startswith('magnet:?') or urlsplit(url).scheme in ('http','https')): raise ApiError('INVALID_TORRENT','种子链接无效')
            if url and not url.startswith('magnet:?'): validate_url(url,allow_query=True)
            if torrent:
                try:
                    raw=base64.b64decode(torrent,validate=True)
                    if not raw or len(raw)>2*1024*1024 or not raw.startswith(b'd'): raise ValueError()
                except ValueError: raise ApiError('INVALID_TORRENT','种子文件格式无效')
            text(b,'save_path',c.get('default_save_path',''),4096); text(b,'name','',200)
            if c['type']=='transmission' and b.get('name') and not torrent: raise ApiError('UNSUPPORTED_OPTION','Transmission 添加链接时不支持自定义名称')
            adapter=self.adapter(c); adapter.connect()
            return {'ok':True,'operation':self.operation(text(b,'request_id'),payload,lambda:self.mutate(c['id'],lambda:adapter.add(b)))}
        match=re.fullmatch(r'/tasks/([^/]+)/([^/]+)(/action)?',path)
        if match:
            did,tid,action=match.groups()
            if tid.lower()=='all' or not re.fullmatch(r'[a-fA-F0-9]{40}|[a-fA-F0-9]{64}|[0-9]+',tid): raise ApiError('INVALID_TASK','必须指定单个有效任务')
            if method=='GET' and not action: return {'ok':True,**self.adapter(self.config(did)).detail(tid)}
            if method=='POST' and action:
                act=text(b,'action'); delete_data=boolean(b,'delete_data')
                if act not in ('pause','resume','delete'): raise ApiError('UNSUPPORTED_ACTION','不支持该操作')
                payload={'downloader_id':did,'task_id':tid,'action':act,'delete_data':delete_data}
                existing=self.existing_operation(text(b,'request_id'),payload)
                if existing: return {'ok':True,'operation':existing}
                adapter=self.adapter(self.config(did)); adapter.connect()
                return {'ok':True,'operation':self.operation(text(b,'request_id'),payload,lambda:self.mutate(did,lambda:adapter.action(tid,act,delete_data)))}
        if path.startswith('/operations/') and method=='GET':
            with self.lock: row=self.db.execute('SELECT receipt FROM operations WHERE id=?',(canonical_uuid(path.split('/')[-1]),)).fetchone()
            if not row: raise ApiError('NOT_FOUND','操作不存在',404)
            return {'ok':True,'operation':json.loads(row[0])}
        if path=='/history' and method=='GET':
            limit=integer(q,'limit',50,1,200)
            with self.lock: items=[json.loads(r[0]) for r in self.db.execute('SELECT receipt FROM operations ORDER BY created_at DESC LIMIT ?',(limit,))]
            return {'ok':True,'items':items}
        raise ApiError('NOT_FOUND','接口不存在或请求方式不受支持',404)

def integer(q,key,default,lo,hi):
    try: value=int(q.get(key,default))
    except (TypeError,ValueError): raise ApiError('INVALID_INPUT',key+' 无效')
    if not lo<=value<=hi: raise ApiError('INVALID_INPUT',key+' 超出范围')
    return value

def make_server(app,host,port,web):
    root=Path(web).resolve()
    class Handler(BaseHTTPRequestHandler):
        server_version='NasDownload'; sys_version=''
        def log_message(self,*args): pass
        def setup(self):
            super().setup(); self.connection.settimeout(15)
            # Absolute deadline also bounds a peer slowly streaming body bytes.
            def expire():
                try: self.connection.shutdown(socket.SHUT_RDWR)
                except OSError: pass
            self.body_deadline=threading.Timer(20,expire); self.body_deadline.daemon=True; self.body_deadline.start()
        def finish(self):
            if hasattr(self,'body_deadline'): self.body_deadline.cancel()
            super().finish()
        def response(self,status,data,cookie=None):
            raw=json.dumps(data,ensure_ascii=False).encode(); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(raw))); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff')
            if cookie: self.send_header('Set-Cookie',cookie)
            self.end_headers(); self.wfile.write(raw)
        def handle_request(self):
            try:
                p=urlsplit(self.path); path=unquote(p.path)
                if not path.startswith('/api/v1/'):
                    if self.command!='GET': raise ApiError('NOT_FOUND','接口不存在',404)
                    file=(root/('index.html' if path=='/' else path.lstrip('/'))).resolve()
                    if not file.is_relative_to(root) or not file.is_file(): raise ApiError('NOT_FOUND','页面不存在',404)
                    raw=file.read_bytes(); self.send_response(200); self.send_header('Content-Type',mimetypes.guess_type(file)[0] or 'application/octet-stream'); self.send_header('Content-Length',str(len(raw))); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Content-Security-Policy',"default-src 'self'; connect-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"); self.end_headers(); self.wfile.write(raw); return
                bearer=self.headers.get('Authorization',''); token=bearer[7:] if bearer.startswith('Bearer ') else ''
                if self.command!='GET':
                    origin=self.headers.get('Origin')
                    if origin:
                        op=urlsplit(origin)
                        if op.scheme not in ('http','https') or op.netloc!=self.headers.get('Host') or op.path not in ('','/'): raise ApiError('BAD_ORIGIN','仅允许同源请求',403)
                    if not token and self.headers.get('X-Nas-Request')!='1': raise ApiError('CSRF','缺少安全请求标识',403)
                if not token:
                    cookies=SimpleCookie(); cookies.load(self.headers.get('Cookie','')); token=cookies.get('ND_SESSION').value if cookies.get('ND_SESSION') else ''
                session=None
                public=path[7:] in ('/health','/setup','/login','/pair')
                if token and not public: session=app.authenticate(token)
                b={}
                if self.command!='GET':
                    if self.headers.get('Transfer-Encoding'): raise ApiError('INVALID_BODY','不支持流式请求',400)
                    length=integer({'length':self.headers.get('Content-Length','0')},'length',0,0,3*1024*1024)
                    if length:
                        if self.headers.get('Content-Type','').split(';')[0]!='application/json': raise ApiError('INVALID_BODY','需要 JSON 请求',415)
                        try: b=json.loads(self.rfile.read(length))
                        except (ValueError,UnicodeError): raise ApiError('INVALID_BODY','JSON 无效')
                    if not isinstance(b,dict): raise ApiError('INVALID_BODY','JSON 必须为对象')
                q={k:v[-1] for k,v in parse_qs(p.query).items()}; result=app.dispatch(self.command,path[7:],q,b,session,self.client_address[0]); cookie=None
                if 'token' in result: cookie='ND_SESSION='+result['token']+'; Path=/; HttpOnly; SameSite=Strict; Max-Age=2592000'+('; Secure' if self.headers.get('Origin','').startswith('https://') else '')
                if path.endswith('/logout'): cookie='ND_SESSION=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0'
                self.response(200,result,cookie)
            except ApiError as e: self.response(e.status,{'ok':False,'error':e.message,'code':e.code})
            except (BrokenPipeError,ConnectionResetError): pass
            except Exception: self.response(500,{'ok':False,'error':'服务处理失败','code':'INTERNAL_ERROR'})
        do_GET=do_POST=do_PATCH=do_DELETE=handle_request
    class ManagedHTTPServer(ThreadingHTTPServer):
        # Explicit bounded draining replaces daemon thread abandonment.
        daemon_threads=True
        def __init__(self,*args):
            self.handlers=threading.Condition(); self.active_handlers=0
            super().__init__(*args)
        def process_request(self,request,address):
            with self.handlers: self.active_handlers+=1
            try: super().process_request(request,address)
            except BaseException:
                with self.handlers: self.active_handlers-=1; self.handlers.notify_all()
                raise
        def process_request_thread(self,request,address):
            try: super().process_request_thread(request,address)
            finally:
                with self.handlers: self.active_handlers-=1; self.handlers.notify_all()
        def drain_handlers(self,timeout=60):
            deadline=time.monotonic()+timeout
            with self.handlers:
                while self.active_handlers:
                    remaining=deadline-time.monotonic()
                    if remaining<=0: return False
                    self.handlers.wait(remaining)
            return True
    return ManagedHTTPServer((host,port),Handler)
