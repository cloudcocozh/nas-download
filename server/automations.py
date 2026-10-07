"""Durable opt-in NAS jobs. Mutations require a lease, ownership and a receipt."""
import base64, hashlib, html, json, math, os, re, secrets, sqlite3, stat, threading, time, uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError, URLError
from .app import ApiError, boolean, canonical_uuid, integer, text, operation_fingerprint
from .adapters import NoRedirect, absolute_download_path, verified_storage_path
from .sites import request

GIB=1024**3
SHANGHAI=timezone(timedelta(hours=8))
KINDS=('hdfans_signin','http_signin','mteam_check','brush')

def parse_attendance(page):
    low=page.lower(); visible=html.unescape(re.sub('<[^>]+>',' ',re.sub(r'<(script|style|template)\b[^>]*>.*?</\1\s*>',' ',page,flags=re.I|re.S)))
    if any(x in low for x in ('cf-chl-','captcha','turnstile','checking your browser','just a moment')) or '验证码' in visible or '驗證碼' in visible:
        return {'status':'challenge','message':'站点要求人工验证，请在浏览器处理'}
    if any(x in visible for x in ('未登录','未登入')) or (re.search(r'name\s*=\s*["\x27]username',low) and re.search(r'name\s*=\s*["\x27]password',low)):
        return {'status':'auth_failure','message':'Cookie 已失效，请重新登录并更新 Cookie'}
    if any(x in visible for x in ('今日已签','今天已签','今天已经签到','今日已经签到','请勿重复签到','今日已簽')):
        return {'status':'already_signed','message':'今天已经签到'}
    if any(x in visible for x in ('签到成功','簽到成功','本次签到获得')):
        return {'status':'success','message':'签到成功'}
    return {'status':'unknown','message':'未识别到明确签到结果，请人工核查，不自动重试'}

def hdfans_signin(cookie):
    req=Request('https://hdfans.org/attendance.php',headers={'Cookie':cookie,'User-Agent':'NasDownload/1','Referer':'https://hdfans.org/','Accept':'text/html'})
    try:
        with build_opener(ProxyHandler({}),NoRedirect()).open(req,timeout=12) as response:
            raw=response.read(2*1024*1024+1)
            if len(raw)>2*1024*1024: return {'status':'unknown','message':'站点响应过大，请人工核查'}
            try: page=raw.decode('utf-8')
            except UnicodeDecodeError: page=raw.decode('gb18030',errors='replace')
            return parse_attendance(page)
    except HTTPError as e:
        with e:
            # Only inspect challenge markers; never store response bodies or redirects.
            parsed=parse_attendance(e.read(128*1024).decode('utf-8',errors='replace'))
            if parsed['status']=='challenge': return parsed
            if e.code in (301,302,303,307,308,401,403): return {'status':'auth_failure','message':'站点拒绝认证或要求浏览器登录'}
        return {'status':'unknown','message':'站点拒绝签到请求，请人工核查'}
    except (OSError,URLError,TimeoutError): return {'status':'uncertain','message':'签到结果不确定，今日不自动重试'}

def torrent_manifest(raw):
    """Hash exact v1 info bytes; reject ambiguous/unsupported metainfo before add."""
    spans={}; nodes=0
    def parse(pos,depth=0,top=False):
        nonlocal nodes
        nodes+=1
        if depth>50 or nodes>100000 or pos>=len(raw): raise ValueError()
        c=raw[pos:pos+1]
        if c==b'i':
            end=raw.index(b'e',pos); token=raw[pos+1:end]
            if not re.fullmatch(rb'0|-?[1-9][0-9]*',token): raise ValueError()
            return int(token),end+1
        if c in (b'd',b'l'):
            pos+=1; value={} if c==b'd' else []
            while raw[pos:pos+1]!=b'e':
                item,pos=parse(pos,depth+1)
                if c==b'd':
                    if not isinstance(item,bytes) or item in value: raise ValueError()
                    vstart=pos; val,pos=parse(pos,depth+1); value[item]=val
                    if top: spans[item]=(vstart,pos)
                else: value.append(item)
            return value,pos+1
        end=raw.index(b':',pos); length_token=raw[pos:end]
        if not re.fullmatch(rb'0|[1-9][0-9]*',length_token): raise ValueError()
        length=int(length_token); pos=end+1
        if pos+length>len(raw): raise ValueError()
        return raw[pos:pos+length],pos+length
    try:
        if not isinstance(raw,bytes) or len(raw)>2*1024*1024: raise ValueError()
        root,end=parse(0,top=True); info=root[b'info']
        if end!=len(raw) or not isinstance(info,dict) or not isinstance(info.get(b'pieces'),bytes) or len(info[b'pieces'])%20 or not info[b'pieces'] or b'piece length' not in info: raise ValueError()
        def safe_component(value):
            if not isinstance(value,bytes) or not value or value in (b'.',b'..') or any(c in value for c in (b'/',b'\\',b':')): return False
            decoded=value.decode('utf-8')
            return not any(ord(c)<32 or ord(c)==127 for c in decoded) and not decoded.endswith((' ','.'))
        if not safe_component(info.get(b'name')) or type(info[b'piece length']) is not int or info[b'piece length']<=0: raise ValueError()
        if b'name.utf-8' in info and info[b'name.utf-8']!=info[b'name']: raise ValueError()
        if b'symlink path' in info or b'l' in info.get(b'attr',b''): raise ValueError()
        name=info[b'name'].decode('utf-8'); files=[]
        if b'files' in info:
            if b'length' in info or not isinstance(info[b'files'],list) or not info[b'files']: raise ValueError()
            sizes=[]
            for file in info[b'files']:
                if not isinstance(file,dict) or not isinstance(file.get(b'path'),list) or not file[b'path'] or not all(safe_component(p) for p in file[b'path']): raise ValueError()
                if b'symlink path' in file or b'l' in file.get(b'attr',b'') or b'path.utf-8' in file and file[b'path.utf-8']!=file[b'path']: raise ValueError()
                sizes.append(file.get(b'length'))
                files.append({'name':name+'/'+('/'.join(p.decode('utf-8') for p in file[b'path'])),'size':file.get(b'length')})
        else:
            sizes=[info.get(b'length')]; files=[{'name':name,'size':info.get(b'length')}]
        if any(type(n) is not int or n<0 for n in sizes) or sum(sizes)<=0: raise ValueError()
        paths=sorted(f['name'].casefold() for f in files)
        pathset=set(paths)
        if len(pathset)!=len(paths) or any('/'.join(path.split('/')[:n]) in pathset for path in paths for n in range(1,len(path.split('/')))): raise ValueError()
        if len(info[b'pieces'])//20!=(sum(sizes)+info[b'piece length']-1)//info[b'piece length']: raise ValueError()
        a,b=spans[b'info']; return hashlib.sha1(raw[a:b]).hexdigest(),sum(sizes),files
    except (ValueError,TypeError,KeyError,IndexError,RecursionError,UnicodeError): raise ApiError('INVALID_TORRENT','不支持或无效的种子信息；自动化要求有效的 v1 哈希与安全文件清单',502)

def torrent_identity(raw): return torrent_manifest(raw)[:2]

def torrent_hash(raw): return torrent_identity(raw)[0]

def vip_expiry(profile):
    if not isinstance(profile,dict): return 0
    if isinstance(profile.get('memberStatus'),dict): profile=profile['memberStatus']
    # Never infer VIP from a user class, badge, username or API success.
    if profile.get('vip') is not True: return 0
    value=profile.get('vipUntil') or profile.get('vipEndTime') or profile.get('vipExpireTime')
    if not value: return 0
    try:
        if isinstance(value,(int,float)) or str(value).isdigit():
            stamp=float(value); return stamp/1000 if stamp>10**12 else stamp
        dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return (dt if dt.tzinfo else dt.replace(tzinfo=SHANGHAI)).timestamp()
    except (ValueError,TypeError,OverflowError): return 0

class Cancelled(Exception): pass

class AutomationService:
    def __init__(self,app):
        self.app=app; self.owner=str(uuid.uuid4()); self.halt=threading.Event(); self.thread=None
        self.pool=ThreadPoolExecutor(max_workers=2,thread_name_prefix='automation'); self.futures={}; self.gates={}; self.download_gates={}; self.local_lock=threading.RLock()
        with app.lock:
            app.db.executescript('''
            CREATE TABLE IF NOT EXISTS automations(id TEXT PRIMARY KEY,config TEXT NOT NULL,enabled INTEGER NOT NULL,generation INTEGER NOT NULL,next_run REAL NOT NULL,last_status TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS automation_runs(id TEXT PRIMARY KEY,automation_id TEXT NOT NULL,generation INTEGER NOT NULL,dry_run INTEGER NOT NULL,status TEXT NOT NULL,created_at REAL NOT NULL,started_at REAL,finished_at REAL,result TEXT NOT NULL,scheduled INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS automation_creates(id TEXT PRIMARY KEY,fingerprint TEXT NOT NULL,automation_id TEXT NOT NULL,receipt TEXT NOT NULL);
            CREATE UNIQUE INDEX IF NOT EXISTS automation_active ON automation_runs(automation_id) WHERE status IN ('queued','running');
            CREATE TABLE IF NOT EXISTS automation_daily(automation_id TEXT,day TEXT,run_id TEXT NOT NULL,PRIMARY KEY(automation_id,day));
            CREATE TABLE IF NOT EXISTS automation_lease(id INTEGER PRIMARY KEY,owner TEXT NOT NULL,expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS automation_intents(id TEXT PRIMARY KEY,automation_id TEXT,downloader_id TEXT,info_hash TEXT,action TEXT,status TEXT NOT NULL,task_id TEXT,marker TEXT,created_at REAL,UNIQUE(downloader_id,info_hash,action));
            CREATE TABLE IF NOT EXISTS automation_owned(automation_id TEXT,downloader_id TEXT,info_hash TEXT,task_id TEXT,marker TEXT,added_at REAL,size INTEGER,obligations TEXT NOT NULL,state TEXT NOT NULL,PRIMARY KEY(downloader_id,info_hash));
            CREATE TABLE IF NOT EXISTS automation_protections(automation_id TEXT,info_hash TEXT,reason TEXT,PRIMARY KEY(automation_id,info_hash));
            CREATE TABLE IF NOT EXISTS automation_samples(downloader_id TEXT,info_hash TEXT,at REAL,uploaded INTEGER,PRIMARY KEY(downloader_id,info_hash,at));
            CREATE TABLE IF NOT EXISTS automation_demand_samples(downloader_id TEXT,info_hash TEXT,at REAL,leechers INTEGER,PRIMARY KEY(downloader_id,info_hash,at));
            CREATE TABLE IF NOT EXISTS automation_storage(downloader_id TEXT,info_hash TEXT,metadata TEXT NOT NULL,PRIMARY KEY(downloader_id,info_hash));
            CREATE TABLE IF NOT EXISTS automation_intent_metadata(id TEXT PRIMARY KEY,metadata TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS automation_intent_history(id TEXT PRIMARY KEY,receipt TEXT NOT NULL);
            '''); app.db.commit()
            if 'scheduled' not in {r['name'] for r in app.db.execute('PRAGMA table_info(automation_runs)')}:
                # Legacy queued jobs did not identify their origin; keep them in
                # the daily window conservatively rather than executing overnight.
                app.db.execute('ALTER TABLE automation_runs ADD COLUMN scheduled INTEGER NOT NULL DEFAULT 1'); app.db.commit()
    def _gate(self,aid):
        with self.local_lock: return self.gates.setdefault(aid,threading.RLock())
    def _config(self,aid):
        with self.app.lock: row=self.app.db.execute('SELECT * FROM automations WHERE id=?',(aid,)).fetchone()
        if not row: raise ApiError('NOT_FOUND','自动任务不存在',404)
        return json.loads(self.app.cipher.decrypt(row['config'].encode())),dict(row)
    def get(self,aid):
        c,row=self._config(aid); flags={key:bool(c.get(key)) for key in ('cookie','headers_json','request_body')}; [c.pop(key,None) for key in flags]
        with self.app.lock: latest=self.app.db.execute('SELECT MAX(created_at) FROM automation_runs WHERE automation_id=?',(aid,)).fetchone()[0]
        return c|{'has_cookie':flags['cookie'],'has_headers_json':flags['headers_json'],'has_request_body':flags['request_body'],'next_run':row['next_run'],'last_status':row['last_status'],'last_run_at':latest}
    def list(self):
        with self.app.lock: ids=[r[0] for r in self.app.db.execute('SELECT id FROM automations ORDER BY rowid')]
        return [self.get(i) for i in ids]
    @staticmethod
    def _window(c,now):
        day=datetime.fromtimestamp(now,SHANGHAI).replace(hour=0,minute=0,second=0,microsecond=0)
        start=sum(int(v)*m for v,m in zip(c['window_start'].split(':'),(60,1)))*60
        end=sum(int(v)*m for v,m in zip(c['window_end'].split(':'),(60,1)))*60
        return day.timestamp()+start,day.timestamp()+end
    def _next(self,c,now=None,after_today=False):
        now=time.time() if now is None else now
        if c['kind']=='brush': return now+c['interval_minutes']*60
        start,end=self._window(c,now)
        if after_today or now>=end: start+=86400; end+=86400
        lower=max(start,now)
        # Fractional wall-clock values must never round beyond the right endpoint.
        return lower+secrets.randbelow(1000000)/1000000*(end-lower)
    def create(self,b):
        if 'request_id' not in b: return self.save(b)
        rid=canonical_uuid(text(b,'request_id')); fingerprint=operation_fingerprint(b)
        with self._gate('new'),self.app.lock:
            self.app.db.execute('BEGIN IMMEDIATE')
            try:
                existing=self.app.db.execute('SELECT * FROM automation_creates WHERE id=?',(rid,)).fetchone()
                if existing:
                    if existing['fingerprint']!=fingerprint: raise ApiError('REQUEST_ID_CONFLICT','同一创建请求编号不能用于不同配置',409)
                    self.app.db.commit(); return json.loads(existing['receipt'])
                item=self.save(b,_commit=False)
                self.app.db.execute('INSERT INTO automation_creates VALUES(?,?,?,?)',(rid,fingerprint,item['id'],json.dumps(item)))
                self.app.db.commit(); return item
            except Exception: self.app.db.rollback(); raise
    def save(self,b,aid=None,_commit=True):
        with self._gate(aid or 'new'),self.app.lock:
            old,row=self._config(aid) if aid else ({},{})
            c=old|b; kind=text(c,'kind',maximum=30)
            if kind not in KINDS or old and kind!=old['kind']: raise ApiError('INVALID_KIND','自动任务类型无效或不可变更')
            clean={'id':aid or str(uuid.uuid4()),'kind':kind,'name':text(c,'name',{'brush':'自动刷流','hdfans_signin':'HDFans 签到','http_signin':'自定义站点签到','mteam_check':'M-Team 账户检查'}[kind],100),'enabled':boolean(c,'enabled',False)}
            if kind!='brush':
                for k,d in (('window_start','08:00'),('window_end','10:00')):
                    value=text(c,k,d,5)
                    if not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]',value): raise ApiError('INVALID_INPUT','每日时间格式应为 HH:mm')
                    clean[k]=value
                if clean['window_start']>=clean['window_end']: raise ApiError('INVALID_INPUT','每日窗口终点必须晚于起点')
            if kind=='http_signin':
                from .signin import clean_config
                clean.update(clean_config(c,old))
            elif kind=='hdfans_signin':
                cookie=text(c,'cookie','',8192) or old.get('cookie','')
                if not cookie or any(ord(x)<32 or ord(x)>255 for x in cookie): raise ApiError('INVALID_COOKIE','请输入有效 Cookie')
                clean['cookie']=cookie
            else:
                sid=text(c,'site_id',maximum=100); site=self.app.sites.config(sid); clean['site_id']=sid
                if kind=='mteam_check' and site['type']!='mteam': raise ApiError('INVALID_SITE','账户检查要求 M-Team 站点')
            if kind=='brush':
                did=c.get('downloader_id'); downloader=self.app.config(did); clean['downloader_id']=downloader['id']
                clean['save_path']=absolute_download_path(text(c,'save_path',downloader.get('default_save_path',''),4096))
                for k,d,lo,hi in [('interval_minutes',10,2,1440),('concurrent',8,1,100),('reserve_gib',100,1,1000000),('capacity_gib',500,1,1000000),('min_seeders',2,2,100000),('min_leechers',3,3,100000),('observe_hours',6,6,8760),('low_upload_kib',32,0,1000000)]: clean[k]=integer(c,k,d,lo,hi)
                for k,d in [('only_free',True),('auto_delete',False),('delete_data',False)]: clean[k]=boolean(c,k,d)
                clean['retention_policy']=text(c,'retention_policy','unknown',30)
                if clean['retention_policy'] not in ('unknown','no_obligation','seed_hours_ratio'): raise ApiError('INVALID_RETENTION','保种策略无效')
                clean['min_seed_hours']=integer(c,'min_seed_hours',72,0,87600)
                ratio=c.get('min_ratio',1.0)
                if isinstance(ratio,bool) or not isinstance(ratio,(int,float)) or not math.isfinite(ratio) or not 0<=ratio<=100000: raise ApiError('INVALID_RETENTION','分享率要求必须是 0 至 100000 的数值')
                clean['min_ratio']=float(ratio); clean['low_leechers']=integer(c,'low_leechers',0,0,100000)
                if clean['delete_data']:
                    if not clean['auto_delete']: raise ApiError('INVALID_RETENTION','删除文件要求同时开启自动清理')
                    verified_storage_path(clean['save_path'],True)
                promos=c.get('promotions',['FREE'])
                if not isinstance(promos,list) or not promos or any(p not in ('FREE','NORMAL','PERCENT_50','PERCENT_70','_2X_FREE','_2X_50','_2X','50%','70%') for p in promos): raise ApiError('INVALID_PROMOTIONS','促销类型无效')
                clean['promotions']=list(dict.fromkeys(promos))
            if not aid and self.app.db.execute('SELECT COUNT(*) FROM automations').fetchone()[0]>=64: raise ApiError('AUTOMATION_LIMIT','最多配置 64 个自动任务',409)
            generation=row.get('generation',0)+1
            next_run=row.get('next_run') if old and all(old.get(k)==clean.get(k) for k in ('kind','window_start','window_end','interval_minutes')) else self._next(clean)
            self.app.db.execute('INSERT OR REPLACE INTO automations VALUES(?,?,?,?,?,?)',(clean['id'],self.app.cipher.encrypt(json.dumps(clean).encode()).decode(),int(clean['enabled']),generation,next_run,row.get('last_status','idle')))
            if old: self.app.db.execute("UPDATE automation_runs SET status='cancelled',finished_at=? WHERE automation_id=? AND status IN ('queued','running')",(time.time(),aid))
            if _commit: self.app.db.commit()
        return self.get(clean['id'])
    def stop(self,aid):
        # Cancellation must still work after a referenced site/engine was removed.
        with self._gate(aid),self.app.lock:
            c,row=self._config(aid); c['enabled']=False
            self.app.db.execute("UPDATE automations SET config=?,enabled=0,generation=generation+1,last_status='cancelled' WHERE id=?",(self.app.cipher.encrypt(json.dumps(c).encode()).decode(),aid))
            self.app.db.execute("UPDATE automation_runs SET status='cancelled',finished_at=? WHERE automation_id=? AND status IN ('queued','running')",(time.time(),aid)); self.app.db.commit()
        return self.get(aid)
    def enqueue(self,aid,rid,dry_run=True,scheduled=False):
        rid=canonical_uuid(rid)
        if type(dry_run) is not bool: raise ApiError('INVALID_INPUT','dry_run 必须为布尔值')
        with self.app.lock:
            existing=self.app.db.execute('SELECT * FROM automation_runs WHERE id=?',(rid,)).fetchone()
            if existing:
                if existing['automation_id']!=aid or bool(existing['dry_run'])!=dry_run: raise ApiError('REQUEST_ID_CONFLICT','同 UUID 不可用于另一操作',409)
                return {'run_id':rid,'status':existing['status']}
            c,row=self._config(aid)
            if not dry_run and not c['enabled']: raise ApiError('TASK_DISABLED','请先启用任务；停用任务仅允许预演',409)
            try:
                self.app.db.execute('INSERT INTO automation_runs(id,automation_id,generation,dry_run,status,created_at,started_at,finished_at,result,scheduled) VALUES(?,?,?,?,?,?,?,?,?,?)',(rid,aid,row['generation'],int(dry_run),'queued',time.time(),None,None,'{}',int(scheduled)))
                self.app.db.execute("UPDATE automations SET last_status='queued' WHERE id=?",(aid,)); self.app.db.commit()
            except sqlite3.IntegrityError:
                self.app.db.rollback(); raise ApiError('TASK_BUSY','此任务已有运行，请先等待或停止',409)
        return {'run_id':rid,'status':'queued'}
    def run(self,rid):
        with self.app.lock: row=self.app.db.execute('SELECT * FROM automation_runs WHERE id=?',(rid,)).fetchone()
        if not row: raise ApiError('NOT_FOUND','运行记录不存在',404)
        return dict(row)|{'result':json.loads(row['result']),'dry_run':bool(row['dry_run']),'scheduled':bool(row['scheduled'])}
    def logs(self,aid,limit=50):
        with self.app.lock: ids=[r[0] for r in self.app.db.execute('SELECT id FROM automation_runs WHERE automation_id=? ORDER BY created_at DESC LIMIT ?',(aid,limit))]
        return [self.run(i) for i in ids]
    def owned(self,aid):
        with self.app.lock:
            rows=list(self.app.db.execute('SELECT o.*,s.metadata FROM automation_owned o LEFT JOIN automation_storage s ON s.downloader_id=o.downloader_id AND s.info_hash=o.info_hash WHERE o.automation_id=?',(aid,)))
            result=[]
            for row in rows:
                value=dict(row); metadata=json.loads(value.pop('metadata') or '{}')
                result.append(value|metadata|{'retention_policy':metadata.get('retention_policy','unknown')})
            return result
    def protections(self,aid):
        with self.app.lock: return [dict(r) for r in self.app.db.execute('SELECT info_hash,reason FROM automation_protections WHERE automation_id=?',(aid,))]
    def protect(self,aid,info_hash,reason='永久保护'):
        self._config(aid)
        if not isinstance(info_hash,str) or not re.fullmatch('[a-fA-F0-9]{40}',info_hash): raise ApiError('INVALID_HASH','请提供 v1 信息哈希')
        if not isinstance(reason,str) or len(reason)>200: raise ApiError('INVALID_INPUT','保护原因无效')
        with self._gate(aid),self.app.lock:
            self.app.db.execute('INSERT OR REPLACE INTO automation_protections VALUES(?,?,?)',(aid,info_hash.lower(),reason)); self.app.db.commit()
    def acquire_lease(self):
        now=time.time()
        with self.app.lock:
            self.app.db.execute("INSERT INTO automation_lease VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET owner=excluded.owner,expires=excluded.expires WHERE automation_lease.expires<? OR automation_lease.owner=?",(self.owner,now+30,now,self.owner)); self.app.db.commit()
            row=self.app.db.execute('SELECT owner FROM automation_lease WHERE id=1').fetchone()
        return row[0]==self.owner
    def start(self):
        if self.thread and self.thread.is_alive(): return
        self.thread=threading.Thread(target=self._loop,name='automation-scheduler',daemon=True); self.thread.start()
    def close(self):
        self.halt.set()
        if self.thread: self.thread.join(timeout=3)
        self.pool.shutdown(wait=True,cancel_futures=True)
        with self.app.lock:
            self.app.db.execute('DELETE FROM automation_lease WHERE owner=?',(self.owner,)); self.app.db.commit()
    def _loop(self):
        recovered=False
        while not self.halt.is_set():
            try:
                if self.acquire_lease():
                    if not recovered:
                        with self.app.lock:
                            self.app.db.execute("UPDATE automations SET last_status='interrupted' WHERE id IN (SELECT automation_id FROM automation_runs WHERE status='running')")
                            self.app.db.execute("UPDATE automation_runs SET status='interrupted',finished_at=?,result=? WHERE status='running'",(time.time(),json.dumps({'reason':'service_restarted','message':'运行中断，已登记的写操作不会重放'}))); self.app.db.commit()
                        recovered=True
                    self._tick()
                else: recovered=False
            except Exception: pass  # Keep service alive; run errors are captured separately.
            self.halt.wait(1)
    def _tick(self):
        now=time.time()
        for c in self.list():
            if c['enabled'] and c['next_run']<=now:
                inside=c['kind']=='brush' or self._window(c,now)[0]<=now<self._window(c,now)[1]
                if inside:
                    try: self.enqueue(c['id'],str(uuid.uuid4()),False,scheduled=True)
                    except ApiError: pass
                with self.app.lock:
                    self.app.db.execute('UPDATE automations SET next_run=? WHERE id=?',(self._next(c,now,c['kind']!='brush' and inside),c['id'])); self.app.db.commit()
        self.futures={k:f for k,f in self.futures.items() if not f.done()}
        with self.app.lock: pending=[r[0] for r in self.app.db.execute("SELECT id FROM automation_runs WHERE status='queued' ORDER BY created_at LIMIT 2")]
        for rid in pending:
            if rid not in self.futures and len(self.futures)<2: self.futures[rid]=self.pool.submit(self._execute,rid)
    def _guard(self,r):
        if self.halt.is_set(): raise Cancelled()
        with self.app.lock:
            row=self.app.db.execute('SELECT enabled,generation FROM automations WHERE id=?',(r['automation_id'],)).fetchone()
            state=self.app.db.execute('SELECT status FROM automation_runs WHERE id=?',(r['id'],)).fetchone()
            lease=self.app.db.execute('SELECT * FROM automation_lease WHERE id=1').fetchone()
        if not row or row['generation']!=r['generation'] or not r['dry_run'] and not row['enabled'] or not state or state[0]!='running': raise Cancelled()
        if not lease or lease['owner']!=self.owner or lease['expires']<=time.time(): raise Cancelled()
    def _execute(self,rid):
        if not self.acquire_lease(): return
        with self.app.lock:
            changed=self.app.db.execute("UPDATE automation_runs SET status='running',started_at=? WHERE id=? AND status='queued'",(time.time(),rid)).rowcount
            if changed: self.app.db.execute("UPDATE automations SET last_status='running' WHERE id=(SELECT automation_id FROM automation_runs WHERE id=?)",(rid,))
            self.app.db.commit()
        if not changed: return
        r=self.run(rid); status='completed'; result={}
        try:
            self._guard(r); c,_=self._config(r['automation_id'])
            if c['kind']=='brush':
                with self.local_lock: gate=self.download_gates.setdefault(str(c['downloader_id']),threading.RLock())
                with gate: result=self._brush(c,r)
            elif r['dry_run']: result={'status':'preview','message':'预演不会调用签到或账户接口'}
            elif r['scheduled'] and not self._window(c,time.time())[0]<=time.time()<self._window(c,time.time())[1]:
                result={'status':'outside_window','reason':'outside_window','message':'已超出每日执行窗口，安排下次窗口，不补发站点请求'}
                with self.app.lock:
                    self.app.db.execute('UPDATE automations SET next_run=? WHERE id=?',(self._next(c),c['id'])); self.app.db.commit()
            else:
                with self._gate(c['id']):
                    self._guard(r); day=datetime.now(SHANGHAI).date().isoformat()
                    with self.app.lock:
                        exists=self.app.db.execute('SELECT 1 FROM automation_daily WHERE automation_id=? AND day=?',(c['id'],day)).fetchone()
                        if not exists: self.app.db.execute('INSERT INTO automation_daily VALUES(?,?,?)',(c['id'],day,rid)); self.app.db.commit()
                    if exists: result={'status':'already_attempted','message':'今日已有实际尝试，不重复执行'}
                    elif c['kind']=='hdfans_signin': result=hdfans_signin(c['cookie'])
                    elif c['kind']=='http_signin':
                        from .signin import run_signin
                        result=run_signin(c)
                    else:
                        site=self.app.sites.config(c['site_id'])
                        if not site['enabled']: raise ApiError('SITE_DISABLED','站点已停用')
                        profile=self.app.sites.adapter(site).api('/member/profile',{},True)
                        result={'status':'account_checked','vip_until':vip_expiry(profile),'message':'账户 API 连接正常；不代表网页登录、签到或保号'}
                if result.get('status') in ('unknown','uncertain','auth_failure','challenge'): status='needs_review'
            if result.get('needs_review'): status='needs_review'
        except Cancelled: status='cancelled'; result={'reason':'stopped','message':'任务已停止'}
        except ApiError as e: status='failed'; result={'code':e.code,'message':e.message}
        except Exception: status='failed'; result={'code':'AUTOMATION_ERROR','message':'后台任务失败，请检查连接与配置；未确认的操作不会重发'}
        with self.app.lock:
            changed=self.app.db.execute("UPDATE automation_runs SET status=?,finished_at=?,result=? WHERE id=? AND status='running'",(status,time.time(),json.dumps(result),rid)).rowcount
            if changed: self.app.db.execute('UPDATE automations SET last_status=? WHERE id=?',(status,r['automation_id']))
            self.app.db.commit()
    @staticmethod
    def _hash(item): return str(item.get('hash') or item.get('id','')).lower()
    def _matches(self,own,item):
        return item and self._hash(item)==own['info_hash'] and str(item['id'])==own['task_id'] and own['marker'] in item.get('tags',[]) and abs(float(item.get('added_at',0))-own['added_at'])<2 and (not own.get('storage_path') or str(item.get('save_path','')).rstrip('/')==own['storage_path'])
    def _sample(self,c,items):
        now=time.time(); by_hash={self._hash(t):t for t in items}
        with self.app.lock:
            for own in self.owned(c['id']):
                item=by_hash.get(own['info_hash'])
                if own['state']=='active' and self._matches(own,item):
                    self.app.db.execute('INSERT OR IGNORE INTO automation_samples VALUES(?,?,?,?)',(str(c['downloader_id']),own['info_hash'],now,int(item.get('uploaded',0))))
                    self.app.db.execute('INSERT OR IGNORE INTO automation_demand_samples VALUES(?,?,?,?)',(str(c['downloader_id']),own['info_hash'],now,int(item.get('swarm_leechers',-1))))
            self.app.db.execute('DELETE FROM automation_samples WHERE at<?',(now-7200,))
            self.app.db.execute('DELETE FROM automation_demand_samples WHERE at<?',(now-7200,)); self.app.db.commit()
    def _reconcile(self,c,items,downloader=None):
        """Observe late effects using durable tokens. Never retry any request."""
        by_hash={self._hash(t):t for t in items}; resolved=[]
        with self.app.lock:
            intents=list(self.app.db.execute("SELECT * FROM automation_intents WHERE downloader_id=? AND status='uncertain'",(str(c['downloader_id']),)))
            for op in intents:
                item=by_hash.get(op['info_hash'])
                if op['action']=='add':
                    if not item or op['marker'] not in item.get('tags',[]) or float(item.get('added_at',0))<op['created_at']-2 or int(item.get('size',0))<=0: continue
                    stored=self.app.db.execute('SELECT metadata FROM automation_intent_metadata WHERE id=?',(op['id'],)).fetchone()
                    metadata=json.loads(stored['metadata']) if stored else {}
                    if metadata and (str(item.get('save_path','')).rstrip('/')!=metadata['storage_path'] or int(item['size'])!=sum(f['size'] for f in metadata['files'])): continue
                    self.app.db.execute('INSERT OR REPLACE INTO automation_owned VALUES(?,?,?,?,?,?,?,?,?)',(op['automation_id'],op['downloader_id'],op['info_hash'],str(item['id']),op['marker'],float(item['added_at']),int(item['size']),'unknown','active'))
                    if metadata: self.app.db.execute('INSERT OR REPLACE INTO automation_storage VALUES(?,?,?)',(op['downloader_id'],op['info_hash'],json.dumps(metadata)))
                    self.app.db.execute('DELETE FROM automation_samples WHERE downloader_id=? AND info_hash=?',(op['downloader_id'],op['info_hash']))
                    self.app.db.execute('DELETE FROM automation_demand_samples WHERE downloader_id=? AND info_hash=?',(op['downloader_id'],op['info_hash']))
                    self.app.db.execute("UPDATE automation_intents SET status='completed',task_id=? WHERE id=?",(str(item['id']),op['id']))
                elif op['action']=='delete' and not item:
                    stored=self.app.db.execute('SELECT metadata FROM automation_intent_metadata WHERE id=?',(op['id'],)).fetchone()
                    metadata=json.loads(stored['metadata']) if stored else {}
                    if metadata.get('delete_data'):
                        if not self._data_gone(metadata['storage_path']) or downloader is None: continue
                        downloader.automation_space(c['save_path'])
                    self.app.db.execute("UPDATE automation_owned SET state='removed' WHERE downloader_id=? AND info_hash=?",(op['downloader_id'],op['info_hash']))
                    self.app.db.execute("UPDATE automation_intents SET status='completed' WHERE id=?",(op['id'],))
                else: continue
                resolved.append(op['id'])
            self.app.db.commit()
        return resolved
    @staticmethod
    def _obligation_reason(own,item):
        policy=own.get('retention_policy','unknown')
        if policy=='no_obligation' or own['obligations']=='verified_clear': return None
        if policy!='seed_hours_ratio': return 'obligations_unknown'
        seconds=item.get('seeding_seconds'); ratio=item.get('ratio')
        if type(seconds) not in (int,float) or not math.isfinite(seconds) or seconds<own.get('min_seed_hours',72)*3600: return 'seed_hours_required'
        if type(ratio) not in (int,float) or not math.isfinite(ratio) or ratio<own.get('min_ratio',1): return 'share_ratio_required'
        return None
    def _data_safety(self,c,own,item,downloader,items):
        """Only downloader APIs delete data; local mount is used for proof only."""
        target=own.get('storage_path',''); expected=c['save_path'].rstrip('/')+'/nd-brush/'+c['id']+'/'+own['info_hash']
        if target!=expected or not own.get('files'): return 'storage_unregistered'
        try:
            local=verified_storage_path(target,True); device=local.stat().st_dev
            detail=downloader.detail(own['task_id'])
            if not self._matches(own,detail.get('item')): return 'identity_changed'
            expected_files={f['name']:f['size'] for f in own['files']}
            if any(not self._safe_relative_file(name) for name in expected_files): return 'storage_unregistered'
            actual_files={f['name']:f['size'] for f in detail.get('files',[])}
            if actual_files!=expected_files or len(detail.get('files',[]))!=len(expected_files): return 'files_changed'
            for other in items:
                if self._hash(other)==own['info_hash'] and str(other['id'])==own['task_id']: continue
                path=absolute_download_path(other.get('save_path',''))
                if path==target or path.startswith(target+'/'): return 'shared_storage'
                if target.startswith(path.rstrip('/')+'/'):
                    other_detail=downloader.detail(str(other['id']))
                    if not other_detail.get('files'): return 'shared_storage_unverified'
                    for file in other_detail['files']:
                        name=file.get('name','')
                        if not self._safe_relative_file(name): return 'shared_storage_unverified'
                        full=path.rstrip('/')+'/'+name
                        if full==target or full.startswith(target+'/') or target.startswith(full+'/'): return 'shared_storage'
            seen=set()
            expected_dirs={'/'.join(name.split('/')[:n]) for name in expected_files for n in range(1,len(name.split('/')))}
            for directory,dirs,files in os.walk(local,followlinks=False):
                for name in dirs+files:
                    path=os.path.join(directory,name); info=os.lstat(path)
                    if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0) or info.st_dev!=device: return 'storage_link_or_mount'
                    rel=os.path.relpath(path,local).replace(os.sep,'/')
                    if name in dirs and rel not in expected_dirs: return 'storage_files_unverified'
                    if name in files:
                        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or rel not in expected_files or info.st_size!=expected_files[rel]: return 'storage_files_unverified'
                        seen.add(rel)
            if seen!=set(expected_files): return 'storage_files_unverified'
        except (ApiError,OSError,KeyError,TypeError,ValueError): return 'storage_unverified'
        return None
    @staticmethod
    def _safe_relative_file(name):
        return isinstance(name,str) and bool(name) and not name.startswith('/') and '\\' not in name and ':' not in name and all(p and p not in ('.','..') and not p.endswith((' ','.')) for p in name.split('/')) and not any(ord(c)<32 or ord(c)==127 for c in name)
    @staticmethod
    def _data_gone(storage):
        try:
            local=verified_storage_path(storage)
            if not local.exists(): return True
            for directory,dirs,files in os.walk(local,followlinks=False):
                if files or any(os.path.islink(os.path.join(directory,name)) for name in dirs): return False
            return True
        except (ApiError,OSError): return False
    def _retire(self,c,r,downloader,items):
        protected={p['info_hash'] for p in self.protections(c['id'])}; by_hash={self._hash(t):t for t in items}; decisions=[]; chosen=False
        for own in self.owned(c['id']):
            item=by_hash.get(own['info_hash']); reason=None
            if own['state']!='active': continue
            if own['info_hash'] in protected: reason='permanent_protection'
            elif not self._matches(own,item): reason='identity_changed'
            elif self._obligation_reason(own,item): reason=self._obligation_reason(own,item)
            elif time.time()-own['added_at']<c['observe_hours']*3600: reason='observation_window'
            elif not math.isfinite(float(item.get('progress',0))) or item.get('progress',0)<1: reason='incomplete'
            elif not math.isfinite(float(item.get('upload_speed',0))): reason='upload_measurement_unknown'
            elif item.get('state') in ('error','checking','queued','paused'): reason='task_not_seeding'
            else:
                with self.app.lock:
                    samples=list(self.app.db.execute('SELECT at,uploaded FROM automation_samples WHERE downloader_id=? AND info_hash=? AND at>=? ORDER BY at',(own['downloader_id'],own['info_hash'],time.time()-3900)))
                    demand=list(self.app.db.execute('SELECT at,leechers FROM automation_demand_samples WHERE downloader_id=? AND info_hash=? AND at>=? ORDER BY at',(own['downloader_id'],own['info_hash'],time.time()-3900)))
                if len(samples)<2 or samples[-1]['at']-samples[0]['at']<3500 or any(b['uploaded']<a['uploaded'] for a,b in zip(samples,samples[1:])): reason='insufficient_hour_samples'
                elif max(float(item.get('upload_speed',0)),(samples[-1]['uploaded']-samples[0]['uploaded'])/(samples[-1]['at']-samples[0]['at']))>=c['low_upload_kib']*1024: reason='uploading_effectively'
                elif c.get('low_leechers',0)>0 and (len(demand)<2 or demand[-1]['at']-demand[0]['at']<3500): reason='insufficient_demand_samples'
                elif c.get('low_leechers',0)>0 and any(s['leechers']<0 for s in demand): reason='demand_unknown'
                elif c.get('low_leechers',0)>0 and any(s['leechers']>c['low_leechers'] for s in demand): reason='active_demand'
                elif c['delete_data']: reason=self._data_safety(c,own,item,downloader,items)
            if reason: decisions.append({'info_hash':own['info_hash'],'reason':reason}); continue
            if chosen: decisions.append({'info_hash':own['info_hash'],'reason':'one_retirement_per_run'}); continue
            chosen=True; decision={'info_hash':own['info_hash'],'reason':'low_upload','would_delete':True,'delete_data':c['delete_data']}; decisions.append(decision)
            if not c['auto_delete'] or r['dry_run']: continue
            with self._gate(c['id']):
                self._guard(r)
                current_items=downloader.tasks(); current=next((t for t in current_items if self._hash(t)==own['info_hash']),None)
                if own['info_hash'] in {p['info_hash'] for p in self.protections(c['id'])}: decision.update(reason='permanent_protection',would_delete=False); continue
                if not self._matches(own,current) or self._obligation_reason(own,current) or current.get('progress',0)<1 or current.get('state') in ('error','checking','queued','paused'):
                    decision.update(reason='identity_or_retention_changed',would_delete=False); continue
                if float(current.get('upload_speed',0))>=c['low_upload_kib']*1024:
                    decision.update(reason='uploading_effectively',would_delete=False); continue
                if c.get('low_leechers',0)>0 and not 0<=int(current.get('swarm_leechers',-1))<=c['low_leechers']:
                    decision.update(reason='active_demand',would_delete=False); continue
                if c['delete_data']:
                    reason=self._data_safety(c,own,current,downloader,current_items)
                    if reason: decision.update(reason=reason,would_delete=False); continue
                op=str(uuid.uuid4())
                with self.app.lock:
                    try:
                        self.app.db.execute('INSERT INTO automation_intents VALUES(?,?,?,?,?,?,?,?,?)',(op,c['id'],str(c['downloader_id']),own['info_hash'],'delete','uncertain',own['task_id'],own['marker'],time.time()))
                        self.app.db.execute('INSERT INTO automation_intent_metadata VALUES(?,?)',(op,json.dumps({'delete_data':c['delete_data'],'storage_path':own.get('storage_path','')})))
                        # Persist the removed candidate's admission metrics. Readmission
                        # needs improvement, never merely elapsed wall-clock time.
                        stored=self.app.db.execute('SELECT metadata FROM automation_storage WHERE downloader_id=? AND info_hash=?',(str(c['downloader_id']),own['info_hash'])).fetchone()
                        if stored:
                            metadata=json.loads(stored['metadata']); metadata['retired_metrics']=metadata.get('selection_metrics',{}); metadata['retired_with_data']=c['delete_data']
                            self.app.db.execute('UPDATE automation_storage SET metadata=? WHERE downloader_id=? AND info_hash=?',(json.dumps(metadata),str(c['downloader_id']),own['info_hash']))
                        self.app.db.commit()
                    except sqlite3.IntegrityError: self.app.db.rollback(); decision.update(reason='prior_delete_intent',would_delete=False); continue
                self._guard(r)
                try:
                    self.app.mutate(c['downloader_id'],lambda:downloader.action(own['task_id'],'delete',c['delete_data']))
                    remaining=downloader.tasks()
                    if any(self._hash(t)==own['info_hash'] for t in remaining): raise ValueError()
                    if c['delete_data'] and not self._data_gone(own['storage_path']): raise ValueError()
                    # This is the current measured free space, not an estimate based
                    # on the deleted torrent's size or an HTTP success response.
                    decision['free_bytes_after']=downloader.automation_space(c['save_path'])
                    with self.app.lock:
                        self.app.db.execute("UPDATE automation_intents SET status='completed' WHERE id=?",(op,)); self.app.db.execute("UPDATE automation_owned SET state='removed' WHERE downloader_id=? AND info_hash=?",(str(c['downloader_id']),own['info_hash'])); self.app.db.commit()
                    decision['deleted']=True
                except Exception: decision['needs_review']=True
        return decisions
    def _brush(self,c,r):
        self._guard(r); site=self.app.sites.config(c['site_id'])
        if not site['enabled']: raise ApiError('SITE_DISABLED','站点已停用')
        downloader=self.app.adapter(self.app.config(c['downloader_id'])); downloader.connect(); items=downloader.tasks()
        resolved=self._reconcile(c,items,downloader)
        with self.app.lock: pending=self.app.db.execute("SELECT 1 FROM automation_intents WHERE downloader_id=? AND status='uncertain'",(str(c['downloader_id']),)).fetchone()
        if pending: return {'would_add':[],'retention':[],'reconciled_operations':resolved,'reason':'uncertain_operation','needs_review':True,'message':'已有未确认的写操作，请人工检查；不会重发'}
        self._sample(c,items); decisions=self._retire(c,r,downloader,items)
        report={'would_add':[],'retention':decisions,'reconciled_operations':resolved}
        if any(d.get('needs_review') for d in decisions): return report|{'needs_review':True}
        # Removal invalidates the old snapshot, including paused/manual downloads.
        if any(d.get('deleted') for d in decisions): items=downloader.tasks()
        # An unknown previous add still reserves a slot and its full candidate size.
        with self.app.lock: uncertain=list(self.app.db.execute("SELECT * FROM automation_intents WHERE downloader_id=? AND status='uncertain'",(str(c['downloader_id']),)))
        if uncertain: return report|{'reason':'uncertain_operation','needs_review':True,'message':'已有未确认的写操作，请人工检查；禁止继续新增'}
        incomplete=[t for t in items if float(t.get('progress',0))<1]
        if len(incomplete)>=c['concurrent']: return report|{'reason':'concurrency_limit'}
        owned=self.owned(c['id']); occupied=sum(t['size'] for t in owned if t['state']=='active' or t.get('storage_path') and not t.get('retired_with_data'))
        free=downloader.automation_space(c['save_path'])
        outstanding=sum(max(0,int(t.get('total_size',t.get('size',0)))*(1-float(t.get('progress',0)))) for t in incomplete)
        budget=min(c['capacity_gib']*GIB-occupied,free-c['reserve_gib']*GIB-outstanding)
        if budget<=0: return report|{'reason':'disk_or_capacity_limit'}
        adapter=self.app.sites.adapter(site); allowed={'FREE','_2X_FREE'}; until=0
        if not c['only_free'] and site['type']=='mteam' and any(p not in allowed for p in c['promotions']):
            try: until=vip_expiry(adapter.api('/member/profile',{},True))
            except ApiError: until=0
            if until>time.time(): allowed.update(c['promotions'])
        report['vip_until']=until; report['effective_promotions']=sorted(allowed)
        rows,_=adapter.search('',1,100)
        candidates=[t for t in rows if t.get('promotion') in allowed and int(t.get('seeders',0))>=c['min_seeders'] and int(t.get('leechers',0))>=c['min_leechers'] and 0<int(t.get('size',0))<=budget]
        candidates.sort(key=lambda t:(int(t['leechers']),int(t['leechers'])/max(1,int(t['seeders']))),reverse=True)
        hashes={self._hash(t) for t in items}
        for candidate in candidates[:20]:
            self._guard(r)
            raw=adapter.torrent(candidate['id']) if site['type']=='mteam' else request(candidate['_url'],maximum=2*1024*1024)
            info_hash,actual_size,files=torrent_manifest(raw)
            if actual_size>budget: continue
            if info_hash in hashes: continue
            if info_hash in {p['info_hash'] for p in self.protections(c['id'])}: continue
            with self.app.lock: prior=list(self.app.db.execute('SELECT * FROM automation_intents WHERE downloader_id=? AND info_hash=?',(str(c['downloader_id']),info_hash)))
            previous=next((o for o in owned if o['info_hash']==info_hash),None)
            if prior and not self._readmission_improved(previous,candidate): continue
            report['would_add']=[candidate['id']]
            if r['dry_run']: return report|{'reason':'preview'}
            with self._gate(c['id']):
                self._guard(r)
                current=downloader.tasks()
                if any(self._hash(t)==info_hash for t in current): continue
                if len([t for t in current if float(t.get('progress',0))<1])>=c['concurrent']: return report|{'reason':'concurrency_limit'}
                fresh_space=downloader.automation_space(c['save_path'])
                fresh_outstanding=sum(max(0,int(t.get('total_size',t.get('size',0)))*(1-float(t.get('progress',0)))) for t in current if float(t.get('progress',0))<1)
                if actual_size>fresh_space-c['reserve_gib']*GIB-fresh_outstanding or actual_size>c['capacity_gib']*GIB-occupied: return report|{'reason':'disk_or_capacity_limit'}
                latest=adapter.detail(candidate['id']) if site['type']=='mteam' else next((t for t in adapter.search('',1,100)[0] if t['id']==candidate['id']),None)
                if not latest or latest.get('promotion') not in allowed: return report|{'reason':'promotion_changed'}
                if int(latest.get('seeders',0))<c['min_seeders'] or int(latest.get('leechers',0))<c['min_leechers']: return report|{'reason':'demand_changed'}
                if prior and not self._readmission_improved(previous,latest): continue
                if latest['promotion'] not in ('FREE','_2X_FREE') and until<=time.time()+60: return report|{'reason':'vip_expired'}
                operation=str(uuid.uuid4()); marker='nd-auto-'+operation; now=time.time()
                storage=c['save_path'].rstrip('/')+'/nd-brush/'+c['id']+'/'+info_hash
                if os.environ.get('ND_BRUSH_VERIFY_ROOT') and os.environ.get('ND_BRUSH_VERIFY_MOUNT'):
                    local=verified_storage_path(storage)
                    if local.exists() and any(local.iterdir()): return report|{'reason':'storage_not_empty','needs_review':True}
                metadata={'storage_path':storage,'files':files,'retention_policy':c.get('retention_policy','unknown'),'min_seed_hours':c.get('min_seed_hours',72),'min_ratio':c.get('min_ratio',1.0),'site_id':c['site_id'],'source_id':str(candidate['id']),'selection_metrics':{'seeders':int(latest['seeders']),'leechers':int(latest['leechers'])}}
                with self.app.lock:
                    try:
                        if prior:
                            for old in prior: self.app.db.execute('INSERT OR IGNORE INTO automation_intent_history VALUES(?,?)',(old['id'],json.dumps(dict(old))))
                            self.app.db.execute("DELETE FROM automation_intents WHERE downloader_id=? AND info_hash=? AND status='completed'",(str(c['downloader_id']),info_hash))
                        self.app.db.execute('INSERT INTO automation_intents VALUES(?,?,?,?,?,?,?,?,?)',(operation,c['id'],str(c['downloader_id']),info_hash,'add','uncertain',None,marker,now))
                        self.app.db.execute('INSERT INTO automation_intent_metadata VALUES(?,?)',(operation,json.dumps(metadata))); self.app.db.commit()
                    except sqlite3.IntegrityError: self.app.db.rollback(); continue
                self._guard(r)
                payload={'torrent_base64':base64.b64encode(raw).decode(),'save_path':storage,'paused':False,'tags':[marker],'automation_managed':True}
                try:
                    response=self.app.mutate(c['downloader_id'],lambda:downloader.add(payload))
                    # Transmission reports duplicate explicitly. Never claim that task.
                    if isinstance(response,dict) and 'torrent-duplicate' in response: raise ValueError()
                    added=next((t for t in downloader.tasks() if self._hash(t)==info_hash and marker in t.get('tags',[])),None)
                    if not added or float(added.get('added_at',0))<now-2 or added.get('save_path','').rstrip('/')!=storage or int(added.get('size',0))!=actual_size: raise ValueError()
                    with self.app.lock:
                        self.app.db.execute('INSERT OR REPLACE INTO automation_owned VALUES(?,?,?,?,?,?,?,?,?)',(c['id'],str(c['downloader_id']),info_hash,str(added['id']),marker,float(added.get('added_at',now)),actual_size,'unknown','active'))
                        self.app.db.execute('INSERT OR REPLACE INTO automation_storage VALUES(?,?,?)',(str(c['downloader_id']),info_hash,json.dumps(metadata)))
                        self.app.db.execute('DELETE FROM automation_samples WHERE downloader_id=? AND info_hash=?',(str(c['downloader_id']),info_hash))
                        self.app.db.execute('DELETE FROM automation_demand_samples WHERE downloader_id=? AND info_hash=?',(str(c['downloader_id']),info_hash))
                        self.app.db.execute("UPDATE automation_intents SET status='completed',task_id=? WHERE id=?",(str(added['id']),operation)); self.app.db.commit()
                    return report|{'reason':'added','operation_id':operation,'task_id':str(added['id'])}
                except Exception: return report|{'reason':'uncertain_add','needs_review':True,'operation_id':operation,'message':'下载器新增结果未确认；票据已保存，不会重复提交'}
        return report|{'reason':'no_eligible_candidates'}
    @staticmethod
    def _readmission_improved(previous,candidate):
        if not previous or previous['state']!='removed' or not previous.get('retired_with_data'): return False
        old=previous.get('retired_metrics',{}); leechers=int(candidate.get('leechers',0)); seeders=int(candidate.get('seeders',0))
        return bool(old) and leechers>int(old.get('leechers',0)) and leechers/max(1,seeders)>int(old.get('leechers',0))/max(1,int(old.get('seeders',0)))
    def dispatch(self,method,path,q,b):
        if path=='/automations':
            if method=='GET': return {'ok':True,'items':self.list()}
            if method=='POST': return {'ok':True,'item':self.create(b)}
        if re.fullmatch('/automation-runs/[^/]+',path) and method=='GET': return {'ok':True,'item':self.run(path.split('/')[-1])}
        match=re.fullmatch('/automations/([^/]+)(?:/(run|stop|logs|owned|protections)(?:/([a-fA-F0-9]{40}))?)?',path)
        if match:
            aid,action,info_hash=match.groups(); self._config(aid)
            if not action:
                if method=='GET': return {'ok':True,'item':self.get(aid)}
                if method=='PATCH': return {'ok':True,'item':self.save(b,aid)}
                if method=='DELETE':
                    self.stop(aid)
                    with self.app.lock: self.app.db.execute('DELETE FROM automations WHERE id=?',(aid,)); self.app.db.commit()
                    return {'ok':True}
            if action=='run' and method=='POST': return {'ok':True,**self.enqueue(aid,text(b,'request_id'),boolean(b,'dry_run',True))}
            if action=='stop' and method=='POST': return {'ok':True,'item':self.stop(aid)}
            if action=='logs' and method=='GET': return {'ok':True,'items':self.logs(aid,integer(q,'limit',50,1,200))}
            if action=='owned' and method=='GET': return {'ok':True,'items':self.owned(aid)}
            if action=='protections':
                if method=='GET': return {'ok':True,'items':self.protections(aid)}
                if method=='POST': self.protect(aid,text(b,'info_hash'),text(b,'reason','永久保护',200)); return {'ok':True}
                if method=='DELETE' and info_hash:
                    with self._gate(aid),self.app.lock: self.app.db.execute('DELETE FROM automation_protections WHERE automation_id=? AND info_hash=?',(aid,info_hash.lower())); self.app.db.commit()
                    return {'ok':True}
        raise ApiError('NOT_FOUND','自动化接口不存在',404)
