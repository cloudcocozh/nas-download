"""Independent, bounded tracker clients. No NAS-tools or imported credentials."""
import base64, json, re, threading, time, uuid, hashlib
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from .app import ApiError, validate_url, text, boolean, integer
from .adapters import NoRedirect

def request(url, body=None, headers=None, maximum=4*1024*1024):
    validate_url(url,allow_query=True)
    try:
        with build_opener(ProxyHandler({}),NoRedirect()).open(Request(url,data=body,headers=headers or {}),timeout=12) as r:
            raw=r.read(maximum+1)
            if len(raw)>maximum: raise ApiError('SITE_RESPONSE','站点返回内容过大',502)
            return raw
    except HTTPError as e:
        code='SITE_AUTH' if e.code in (401,403) else 'SITE_RATE_LIMIT' if e.code==429 else 'SITE_REJECTED'
        raise ApiError(code,'站点拒绝请求，请检查凭据、权限或调用频率',502)
    except (URLError,OSError,TimeoutError): raise ApiError('SITE_UNAVAILABLE','无法连接站点，请检查地址和网络',502)

def number(value):
    try: return max(0,int(value or 0))
    except (ValueError,TypeError): return 0

class MTeam:
    def __init__(self,c): self.c=c
    def api(self,path,data,form=False):
        body=urlencode(data).encode() if form else json.dumps(data).encode()
        raw=request(self.c['url']+path,body,{'x-api-key':self.c['api_key'],'Content-Type':'application/x-www-form-urlencoded' if form else 'application/json','User-Agent':'NasDownload/1'})
        try:
            result=json.loads(raw)
            if str(result.get('code'))!='0': raise ApiError('SITE_REJECTED','M-Team 返回错误，请检查令牌与权限',502)
            return result['data']
        except (ValueError,KeyError,TypeError): raise ApiError('SITE_RESPONSE','M-Team 响应格式无效',502)
    def normalize(self,row):
        status=row.get('status') or {}
        return {'id':str(row['id']),'name':str(row.get('name') or ''),'subtitle':str(row.get('smallDescr') or ''),'size':number(row.get('size')),'seeders':number(status.get('seeders')),'leechers':number(status.get('leechers')),'promotion':str(status.get('discount') or ''),'published':str(row.get('createdDate') or '')}
    def search(self,query,page,limit):
        data=self.api('/torrent/search',{'mode':'normal','keyword':query,'pageNumber':page,'pageSize':limit})
        return [self.normalize(r) for r in data.get('data',[])],number(data.get('total'))
    def detail(self,tid):
        if not re.fullmatch(r'[0-9]{1,20}',tid): raise ApiError('INVALID_TORRENT','资源编号无效')
        row=self.api('/torrent/detail',{'id':tid},True)
        return self.normalize(row)|{'description':str(row.get('descr') or '')[:100000]}
    def torrent(self,tid):
        self.detail(tid)
        url=self.api('/torrent/genDlToken',{'id':tid},True); p=urlsplit(url)
        if p.scheme!='https' or p.hostname not in ('api.m-team.cc','api.m-team.io','fr1.halomt.com') or p.port not in (None,443) or p.username or p.password or p.fragment:
            raise ApiError('SITE_DOWNLOAD_TARGET','站点返回的下载地址不受信任',502)
        if p.hostname.startswith('api.m-team.') and p.path!='/api/rss/dlv2': raise ApiError('SITE_DOWNLOAD_TARGET','下载路径不受信任',502)
        return request(url,maximum=2*1024*1024)

class Torznab:
    def __init__(self,c): self.c=c
    def search(self,query,page,limit):
        raw=request(self.c['url']+'?'+urlencode({'t':'search','q':query,'apikey':self.c['api_key'],'offset':(page-1)*limit,'limit':limit,'extended':1}))
        if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper(): raise ApiError('SITE_RESPONSE','站点 XML 含禁止内容',502)
        try: root=ET.fromstring(raw)
        except ET.ParseError: raise ApiError('SITE_RESPONSE','Torznab XML 无效',502)
        if root.tag=='error': raise ApiError('SITE_REJECTED','Torznab 返回错误，请检查密钥与权限',502)
        items=[]
        for entry in root.findall('./channel/item'):
            attrs={a.get('name'):a.get('value') for a in entry if a.tag.endswith('attr')}
            enclosure=entry.find('enclosure'); url=enclosure.get('url','') if enclosure is not None else entry.findtext('link','')
            # Downloader URLs must stay on the exact configured origin.
            p=urlsplit(url); base=urlsplit(self.c['url'])
            if (p.scheme,p.netloc)!=(base.scheme,base.netloc) or p.username or p.password or p.fragment: continue
            seeders=number(attrs.get('seeders'))
            leechers=number(attrs.get('leechers')) if 'leechers' in attrs else max(0,number(attrs.get('peers'))-seeders)
            factor=attrs.get('downloadvolumefactor'); promotion='FREE' if factor is not None and re.fullmatch(r'0(?:\.0+)?',factor) else ''
            items.append({'id':hashlib.sha256(url.encode()).hexdigest(),'name':entry.findtext('title',''),'subtitle':'','size':number(attrs.get('size') or (enclosure.get('length') if enclosure is not None else 0)),'seeders':seeders,'leechers':leechers,'promotion':promotion,'published':entry.findtext('pubDate',''),'_url':url})
        response=next((e for e in root.iter() if e.tag.endswith('response')),None)
        total=number(response.get('total')) if response is not None else (page-1)*limit+len(items)
        return items,total

class SiteService:
    def __init__(self,app):
        self.app=app; self.jobs={}; self.results={}; self.lock=threading.RLock(); self.pool=ThreadPoolExecutor(max_workers=4)
        with app.lock: app.db.execute('CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY,config TEXT)'); app.db.commit()
    def configs(self):
        with self.app.lock: return [json.loads(self.app.cipher.decrypt(r[0].encode())) for r in self.app.db.execute('SELECT config FROM sites')]
    def config(self,sid):
        c=next((c for c in self.configs() if c['id']==sid),None)
        if not c: raise ApiError('NOT_FOUND','站点不存在',404)
        return c
    def public(self,c): return {k:c[k] for k in ('id','name','type','url','enabled')}|{'has_api_key':bool(c['api_key'])}
    def adapter(self,c): return MTeam(c) if c['type']=='mteam' else Torznab(c)
    def clean(self,item,c): return {k:v for k,v in item.items() if not k.startswith('_')}|{'site_id':c['id'],'site_name':c['name']}
    def search(self,job,configs,query,page,limit):
        def fetch(c):
            if job['cancel'].is_set(): return
            try:
                rows,total=self.adapter(c).search(query,page,limit)
                with self.lock:
                    if job['cancel'].is_set(): return
                    job['items'].extend(self.clean(r,c) for r in rows); job['site_totals'][c['id']]=total
                    for r in rows: self.results[(c['id'],r['id'])]=(time.time(),r)
                    while len(self.results)>4096: del self.results[next(iter(self.results))]
            except ApiError as e:
                with self.lock:
                    if not job['cancel'].is_set(): job['errors'].append({'site_id':c['id'],'code':e.code,'error':e.message})
            except Exception:
                with self.lock: job['errors'].append({'site_id':c['id'],'code':'SITE_RESPONSE','error':'站点响应格式无效'})
        # Separate bounded per-job workers keep polling and cancellation responsive.
        with ThreadPoolExecutor(max_workers=min(4,len(configs))) as pool: list(pool.map(fetch,configs))
        with self.lock: job['status']='cancelled' if job['cancel'].is_set() else 'completed'; job['active']=False
    def dispatch(self,method,path,q,b,session):
        if path=='/sites' and method=='GET': return {'ok':True,'items':[self.public(c) for c in self.configs()]}
        if (path=='/sites' and method=='POST') or (re.fullmatch('/sites/[^/]+',path) and method=='PATCH'):
            old=self.config(path.split('/')[-1]) if method=='PATCH' else {}; c=old|b
            c={k:text(c,k,d,m) for k,d,m in [('name','站点',100),('type',None,20),('url',None,2048),('api_key','',1024)]}|{'id':old.get('id',str(uuid.uuid4())),'enabled':boolean(c,'enabled',True)}
            if c['type'] not in ('mteam','torznab'): raise ApiError('UNSUPPORTED_SITE','支持 M-Team 与 Torznab 站点')
            if old and not c['api_key']: c['api_key']=old['api_key']
            if not c['api_key'] or any(ord(x)<32 for x in c['api_key']): raise ApiError('INVALID_INPUT','请输入有效 API 密钥')
            c['url']=validate_url(c['url'])
            if c['type']=='mteam' and c['url'] not in ('https://api.m-team.cc/api','https://api.m-team.io/api'): raise ApiError('SITE_TARGET','M-Team 仅允许官方 HTTPS API 地址')
            with self.app.lock:
                if not old and len(self.configs())>=16: raise ApiError('SITE_LIMIT','最多配置 16 个站点',409)
                self.app.db.execute('INSERT OR REPLACE INTO sites VALUES(?,?)',(c['id'],self.app.cipher.encrypt(json.dumps(c).encode()).decode())); self.app.db.commit()
            with self.lock: self.results={k:v for k,v in self.results.items() if k[0]!=c['id']}
            return {'ok':True,'item':self.public(c)}
        if re.fullmatch('/sites/[^/]+',path) and method=='DELETE':
            sid=path.split('/')[-1]; self.config(sid)
            with self.app.lock: self.app.db.execute('DELETE FROM sites WHERE id=?',(sid,)); self.app.db.commit()
            with self.lock: self.results={k:v for k,v in self.results.items() if k[0]!=sid}
            return {'ok':True}
        if path=='/searches' and method=='POST':
            query=text(b,'query','',200).strip(); page=integer(b,'page',1,1,1000); limit=integer(b,'limit',30,1,100)
            ids=b.get('site_ids',[])
            if not isinstance(ids,list) or any(not isinstance(i,str) for i in ids): raise ApiError('INVALID_INPUT','site_ids 必须为数组')
            configs=[self.config(i) for i in dict.fromkeys(ids)] if ids else self.configs(); configs=[c for c in configs if c['enabled']]
            if not configs: raise ApiError('NO_SITES','请先配置并启用站点')
            with self.lock:
                now=time.time(); self.jobs={k:v for k,v in self.jobs.items() if now-v['created_at']<600 or v['active']}; self.results={k:v for k,v in self.results.items() if now-v[0]<600}
                if sum(j['active'] for j in self.jobs.values())>=4: raise ApiError('SEARCH_BUSY','搜索繁忙，请等待已有站点请求收尾后重试',429)
                if len(self.jobs)>=128:
                    oldest=next((k for k,v in self.jobs.items() if not v['active']),None)
                    if oldest: del self.jobs[oldest]
                jid=str(uuid.uuid4()); job={'id':jid,'status':'running','active':True,'items':[],'errors':[],'site_totals':{},'page':page,'limit':limit,'created_at':now,'owner':session['id'],'cancel':threading.Event()}; self.jobs[jid]=job
                self.pool.submit(self.search,job,configs,query,page,limit)
            return {'ok':True,'search_id':jid}
        if path.startswith('/searches/') and method in ('GET','DELETE'):
            with self.lock:
                job=self.jobs.get(path.split('/')[-1])
                if not job or job['owner']!=session['id']: raise ApiError('NOT_FOUND','搜索不存在或已过期',404)
                if method=='DELETE': job['cancel'].set(); job['status']='cancelled'; return {'ok':True,'status':'cancelled'}
                offset=integer(q,'offset',0,0,100000); limit=integer(q,'limit',100,1,200)
                return {'ok':True,'search_id':job['id'],'status':job['status'],'items':job['items'][offset:offset+limit],'total':len(job['items']),'site_totals':dict(job['site_totals']),'errors':list(job['errors']),'page':job['page'],'limit':job['limit']}
        match=re.fullmatch('/sites/([^/]+)/torrents/([^/]+)(/download)?',path)
        if match:
            sid,tid,download=match.groups(); c=self.config(sid); adapter=self.adapter(c)
            if method=='GET' and not download:
                if c['type']=='mteam': item=adapter.detail(tid)
                else:
                    cached=self.results.get((sid,tid))
                    if not cached or time.time()-cached[0]>600: raise ApiError('RESULT_EXPIRED','搜索结果过期，请重新搜索',410)
                    item=cached[1]
                return {'ok':True,'item':self.clean(item,c)}
            if method=='POST' and download:
                existing=self.app.existing_operation(text(b,'request_id'),b|{'site_id':sid,'torrent_id':tid})
                if existing: return {'ok':True,'operation':existing}
                config=self.app.config(b.get('downloader_id')); boolean(b,'paused'); text(b,'save_path',config.get('default_save_path',''),4096)
                if c['type']=='mteam': raw=adapter.torrent(tid)
                else:
                    cached=self.results.get((sid,tid))
                    if not cached or time.time()-cached[0]>600: raise ApiError('RESULT_EXPIRED','搜索结果过期，请重新搜索',410)
                    raw=request(cached[1]['_url'],maximum=2*1024*1024)
                if not raw.startswith(b'd'): raise ApiError('INVALID_TORRENT','站点没有返回有效种子文件',502)
                payload=b|{'site_id':sid,'torrent_id':tid}; add={k:v for k,v in b.items() if k in ('save_path','paused')}; add['torrent_base64']=base64.b64encode(raw).decode()
                downloader=self.app.adapter(config); downloader.connect()
                return {'ok':True,'operation':self.app.operation(text(b,'request_id'),payload,lambda:self.app.mutate(config['id'],lambda:downloader.add(add)))}
        raise ApiError('NOT_FOUND','站点接口不存在',404)
