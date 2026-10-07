"""User-configured HTTP attendance. No scripts, redirects, or response-body logs."""
import ipaddress
import json
import re
from urllib.parse import urlsplit, urlencode
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError, URLError
from .app import ApiError, text, integer, validate_url
from .adapters import NoRedirect

SECRETS=('cookie','headers_json','request_body')

def clean_config(data, old=None):
    old=old or {}
    url=text(data,'signin_url',maximum=2048)
    validate_url(url)
    p=urlsplit(url)
    if p.scheme!='https':
        try: local=ipaddress.ip_address(p.hostname)
        except ValueError: raise ApiError('SIGNIN_HTTPS','公网签到地址须使用 HTTPS；局域网 HTTP 请使用数字地址')
        if not(local.is_private or local.is_loopback or local in ipaddress.ip_network('100.64.0.0/10')):
            raise ApiError('SIGNIN_HTTPS','公网签到地址须使用 HTTPS')
    method=text(data,'method','GET',10).upper()
    fmt=text(data,'request_format','form',10)
    if method not in ('GET','POST') or fmt not in ('form','json','text'):
        raise ApiError('SIGNIN_REQUEST','仅支持 GET/POST 与 form/json/text 请求格式')
    result={'signin_url':url,'method':method,'request_format':fmt,
            'expected_status':integer(data,'expected_status',200,200,299)}
    for key,limit in [('cookie',8192),('headers_json',16384),('request_body',32768)]:
        result[key]=text(data,key,'',limit) or old.get(key,'')
    if any(ord(c)<32 or ord(c)>255 for c in result['cookie']): raise ApiError('INVALID_COOKIE','Cookie 格式无效')
    try:
        headers=json.loads(result['headers_json'] or '{}')
        if not isinstance(headers,dict) or len(headers)>30: raise ValueError()
        blocked={'host','content-length','connection','transfer-encoding','proxy-authorization','proxy-connection','upgrade','te','trailer'}
        for name,value in headers.items():
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9-]{0,63}',name) or name.lower() in blocked: raise ValueError()
            if not isinstance(value,str) or len(value)>8192 or any(ord(c)<32 or ord(c)>255 for c in value): raise ValueError()
        if fmt in ('form','json') and result['request_body']:
            body=json.loads(result['request_body'])
            if not isinstance(body,dict): raise ValueError()
            if fmt=='form' and any(isinstance(v,(dict,list)) for v in body.values()): raise ValueError()
        if method=='GET' and fmt=='text' and result['request_body']: raise ValueError()
    except (ValueError,TypeError): raise ApiError('SIGNIN_FORMAT','请求头须为 JSON 文本对象；form/json 正文须为 JSON 对象，GET 不支持原始文本正文')
    for key in ('success_contains','already_contains','failure_contains'):
        result[key]=text(data,key,'',200)
    if not result['success_contains'].strip(): raise ApiError('SIGNIN_SUCCESS','请填写响应中明确代表签到成功的文字，不能仅按 HTTP 200 判断')
    return result

def run_signin(config):
    # Revalidate at execution time; credentials are sent only to this configured origin.
    c=clean_config(config,config)
    headers={'user-agent':'NasDownload/1.2','accept':'text/html,application/json'}
    headers.update({k.lower():v for k,v in json.loads(c['headers_json'] or '{}').items()})
    if c['cookie']: headers['cookie']=c['cookie']
    url=c['signin_url']; body=None; data=c['request_body']
    if c['method']=='GET' and data:
        url+='?'+urlencode(json.loads(data))
    elif c['method']=='POST':
        if c['request_format']=='form': body=urlencode(json.loads(data or '{}')).encode(); headers.setdefault('content-type','application/x-www-form-urlencoded')
        elif c['request_format']=='json': body=(data or '{}').encode(); headers.setdefault('content-type','application/json')
        else: body=data.encode(); headers.setdefault('content-type','text/plain; charset=utf-8')
    try:
        req=Request(url,data=body,headers=headers,method=c['method'])
        with build_opener(ProxyHandler({}),NoRedirect()).open(req,timeout=15) as response:
            raw=response.read(2*1024*1024+1); status=response.status
            if len(raw)>2*1024*1024: return {'status':'unknown','message':'响应过大，未判定成功，请人工核查'}
            encoding=response.headers.get_content_charset() or 'utf-8'
            try: content=raw.decode(encoding)
            except (UnicodeError,LookupError): content=raw.decode('utf-8',errors='replace')
        if status!=c['expected_status']: return {'status':'unknown','message':'响应状态与预期不同，请人工核查'}
        if c['failure_contains'] and c['failure_contains'] in content: return {'status':'auth_failure','message':'响应匹配失败标志，请检查凭据或站点规则'}
        if c['already_contains'] and c['already_contains'] in content: return {'status':'already_signed','message':'响应匹配已签到标志'}
        if c['success_contains'] in content: return {'status':'success','message':'响应匹配配置的签到成功标志'}
        return {'status':'unknown','message':'响应未匹配成功或已签到标志；不自动重试'}
    except HTTPError as error:
        status=error.code; error.close()
        if status in (301,302,303,307,308): return {'status':'auth_failure','message':'站点要求跳转；为保护凭据未跟随，请检查最终签到地址'}
        return {'status':'auth_failure' if status in (401,403) else 'unknown','message':'站点拒绝或未完成请求，请人工核查'}
    except (URLError,OSError,TimeoutError): return {'status':'uncertain','message':'请求结果不确定；今日不自动重发'}
