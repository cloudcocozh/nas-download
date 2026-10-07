package com.nasdownload.app;

import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.text.InputType;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.widget.*;
import org.json.*;
import java.util.*;

/** NAS-owned schedules. The phone never schedules, replays, or stores site cookies. */
final class AutomationUi {
 final MainActivity a;
 AutomationUi(MainActivity activity){a=activity;}
 String path(JSONObject task){return "/automations/"+Api.segment(task.optString("id"));}
 String label(String kind){return kind.equals("brush")?"自动刷流":kind.equals("hdfans_signin")?"HDFans 签到":kind.equals("http_signin")?"自定义签到":"M-Team 账户检查";}
 String retentionLabel(String policy){return policy.equals("no_obligation")?"已声明无保种义务":policy.equals("seed_hours_ratio")?"累计做种小时与分享率同时达标":"未知义务，保持保护";}
 String state(String s){switch(s){case "queued":return "已排队";case "running":return "运行中";case "completed":return "已完成";case "failed":return "失败";case "cancelled":return "已停止";case "interrupted":return "重启中断";case "needs_review":return "需要核查";default:return "未运行";}}
 String time(double seconds){return seconds<=0?"未安排":new java.text.SimpleDateFormat("MM-dd HH:mm",Locale.CHINA).format(new Date((long)(seconds*1000)));}
 void list(){a.screen("签到与刷流");a.body.addView(a.button("‹ 下载任务",a::home));a.body.addView(a.text("任务由 NAS 后台执行，关闭手机仍按计划运行。新任务默认停用，不接管旧任务。实际运行须明确启用。",13,a.muted));a.body.addView(a.button("＋ 创建任务",()->new AlertDialog.Builder(a).setTitle("任务类型").setItems(new String[]{"HDFans 签到","自定义签到","M-Team 账户检查（只读）","自动刷流"},(d,n)->form(null,new String[]{"hdfans_signin","http_signin","mteam_check","brush"}[n])).show()));a.body.addView(a.button("刷新",this::list));a.read("读取后台任务…",()->a.api.request("GET","/automations",null),j->{JSONArray items=j.getJSONArray("items");if(items.length()==0)a.body.addView(a.text("尚未创建任务。配置并保存后，可先使用只读预演核对条件。",14,a.muted));for(int i=0;i<items.length();i++){JSONObject t=items.getJSONObject(i);LinearLayout c=a.card();c.addView(a.text(t.optString("name"),17,a.ink));c.addView(a.text(label(t.optString("kind"))+" · "+(t.optBoolean("enabled")?"已启用":"已停用")+" · "+state(t.optString("last_status"))+"\n下次："+time(t.optDouble("next_run"))+" · 最近："+time(t.optDouble("last_run_at")),13,a.muted));c.addView(a.button("配置 / 运行 / 日志",()->detail(t)));a.body.addView(c);}});}
 void detail(JSONObject task){a.screen(task.optString("name","后台任务"));a.body.addView(a.button("‹ 返回任务列表",this::list));a.body.addView(a.text(label(task.optString("kind"))+" · "+(task.optBoolean("enabled")?"已启用":"已停用")+"\n"+state(task.optString("last_status"))+" · 下次："+time(task.optDouble("next_run")),14,a.muted));a.body.addView(a.button("编辑配置",()->form(task,task.optString("kind"))));a.body.addView(a.button("只读预演（默认）",()->run(task,true)));a.body.addView(a.button("实际运行",()->{if(!task.optBoolean("enabled")){a.error("请先编辑并启用任务；停用任务仅可预演。");return;}new AlertDialog.Builder(a).setTitle("确认实际运行").setMessage(task.optString("kind").equals("mteam_check")?"只检查账户连接及 VIP 到期，不代表签到或保号。":task.optString("kind").equals("brush")?"刷流可能新增任务；开启自动清理后可能移除达标任务，开启删除文件后也可能清理专属目录中的文件。永久保护与文件验证始终生效。":"将按保存的配置向站点发出一次签到请求；不确定结果不自动重试。").setNegativeButton("取消",null).setPositiveButton("执行一次",(d,w)->run(task,false)).show();}));a.body.addView(a.button("停止并停用",()->stop(task)));a.body.addView(a.button("运行日志 / 刷新状态",()->logs(task)));if(task.optString("kind").equals("brush"))a.body.addView(a.button("归属与永久保护",()->protections(task)));a.body.addView(a.text("停止后不发起后续写操作；已发出的请求可能完成或记录为不确定。实际状态请查看日志。",12,a.muted));}
 void stop(JSONObject task){a.read("停止后台任务…",()->a.api.request("POST",path(task)+"/stop",new JSONObject()),j->detail(j.getJSONObject("item")));}
 CheckBox check(LinearLayout f,String title,boolean value){CheckBox c=new CheckBox(a);c.setText(title);c.setChecked(value);f.addView(c);return c;}
 Spinner options(LinearLayout f,String title,JSONArray items,String selected){f.addView(a.text(title,13,a.muted));Spinner s=new Spinner(a);ArrayList<String> names=new ArrayList<>();int pos=0;for(int i=0;i<items.length();i++){JSONObject x=items.optJSONObject(i);names.add(x.optString("name"));if(x.optString("id").equals(selected))pos=i;}s.setAdapter(new ArrayAdapter<>(a,android.R.layout.simple_spinner_dropdown_item,names));s.setSelection(pos);f.addView(s);return s;}
 EditText field(LinearLayout f,String key,String title,String value,boolean secret,boolean multiline){
  EditText input=a.input(f,title,value,secret);input.setTag(key);
  if(multiline){input.setSingleLine(false);input.setMinLines(2);input.setMaxLines(5);input.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_FLAG_MULTI_LINE|(secret?InputType.TYPE_TEXT_VARIATION_PASSWORD|InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS:0));}
  if(secret){input.setSaveEnabled(false);input.setSaveFromParentEnabled(false);input.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO);input.setImeOptions(input.getImeOptions()|EditorInfo.IME_FLAG_NO_PERSONALIZED_LEARNING);}
  return input;
 }
 Spinner choice(LinearLayout f,String key,String title,String[][] values,String selected){
  f.addView(a.text(title,13,a.muted));Spinner spinner=new Spinner(a);spinner.setTag(key);ArrayList<String> labels=new ArrayList<>();int position=0;
  for(int i=0;i<values.length;i++){labels.add(values[i][1]);if(values[i][0].equals(selected))position=i;}
  spinner.setAdapter(new ArrayAdapter<>(a,android.R.layout.simple_spinner_dropdown_item,labels));spinner.setSelection(position);f.addView(spinner);return spinner;
 }
 CheckBox flag(LinearLayout f,String key,String title,boolean value){CheckBox box=check(f,title,value);box.setTag(key);return box;}
 void form(JSONObject old,String kind){
  if(kind.equals("hdfans_signin")||kind.equals("http_signin")){renderForm(old,kind,new JSONArray(),new JSONArray());return;}
  a.read("读取站点和下载器…",()->{JSONObject j=a.json("sites",a.api.request("GET","/sites",null).getJSONArray("items"));j.put("downloaders",a.api.request("GET","/downloaders",null).getJSONArray("items"));return j;},j->renderForm(old,kind,j.getJSONArray("sites"),j.getJSONArray("downloaders")));
 }
 void renderForm(JSONObject old,String kind,JSONArray allSites,JSONArray downloaders){
  JSONObject config=old==null?new JSONObject():old;boolean brush=kind.equals("brush"),custom=kind.equals("http_signin");JSONArray sites=new JSONArray();
  for(int i=0;i<allSites.length();i++){JSONObject s=allSites.optJSONObject(i);if(brush||s.optString("type").equals("mteam"))sites.put(s);}
  a.screen("配置："+label(kind));a.body.addView(a.button("‹ 返回",this::list));LinearLayout f=a.body;
  EditText name=field(f,"name","任务名称",config.optString("name",label(kind)),false,false);
  CheckBox enabled=flag(f,"enabled","启用 NAS 后台定时任务",config.optBoolean("enabled",false));f.addView(a.text("新任务默认停用。启用后服务会自动安排下一次运行。",12,a.muted));
  Map<String,EditText> fields=new LinkedHashMap<>(),secrets=new LinkedHashMap<>();Map<String,CheckBox> booleans=new LinkedHashMap<>();
  final Spinner site=kind.equals("hdfans_signin")||custom?null:options(f,"站点",sites,config.optString("site_id"));
  final Spinner engine=brush?options(f,"下载器",downloaders,config.optString("downloader_id")):null;
  if(kind.equals("hdfans_signin")||custom)secrets.put("cookie",field(f,"cookie",config.optBoolean("has_cookie")?"Cookie（已保存，留空保留）":"Cookie（只传给 NAS，加密保存）","",true,false));
  final Spinner method=custom?choice(f,"method","请求方法",new String[][]{{"GET","GET"},{"POST","POST"}},config.optString("method","GET")):null;
  final Spinner format=custom?choice(f,"request_format","请求格式",new String[][]{{"form","form：JSON 对象转表单"},{"json","json：JSON 正文"},{"text","text：原始文本"}},config.optString("request_format","form")):null;
  if(custom){
   fields.put("signin_url",field(f,"signin_url","签到地址（公网须 HTTPS）",config.optString("signin_url"),false,false));
   secrets.put("headers_json",field(f,"headers_json",config.optBoolean("has_headers_json")?"请求头 JSON（已保存，留空保留）":"请求头 JSON（可选，如 {\"X-Token\":\"…\"}）","",true,true));
   secrets.put("request_body",field(f,"request_body",config.optBoolean("has_request_body")?"请求正文（已保存，留空保留）":"请求正文（form/json 填 JSON 对象，可选）","",true,true));
   fields.put("success_contains",field(f,"success_contains","成功标志（必填，响应中明确表示成功的文字）",config.optString("success_contains"),false,false));
   fields.put("already_contains",field(f,"already_contains","已签到标志（可选）",config.optString("already_contains"),false,false));
   fields.put("failure_contains",field(f,"failure_contains","失败标志（可选，优先判断）",config.optString("failure_contains"),false,false));
   fields.put("expected_status",field(f,"expected_status","预期 HTTP 状态（200–299）",config.optString("expected_status","200"),false,false));
   f.addView(a.text("填写站点明确提供的签到请求及结果标志。Cookie、请求头和正文仅发送给 NAS 加密保存；手机不保存这些内容。GET 的 JSON 对象会转为查询参数；GET 不支持原始文本正文。",13,a.muted));
  }
  final Spinner retention=brush?choice(f,"retention_policy","新任务保种条件",new String[][]{{"unknown","未知：保持保护，不自动清理"},{"no_obligation","我确认该站点无保种义务"},{"seed_hours_ratio","做种小时与分享率均须达标"}},config.optString("retention_policy","unknown")):null;
  if(!brush){
   fields.put("window_start",field(f,"window_start","每日随机窗口开始（北京时间 HH:mm）",config.optString("window_start","08:00"),false,false));
   fields.put("window_end",field(f,"window_end","每日随机窗口结束（北京时间 HH:mm）",config.optString("window_end","10:00"),false,false));
   f.addView(a.text(kind.equals("mteam_check")?"仅检查账户 API 和 VIP 到期；不执行网页登录、签到或保号。":"每天最多一次真实签到尝试；不确定结果不自动重试。更换配置不会增加当天尝试次数。遇验证码请人工核查。",13,a.muted));
  }else{
   String[][] values={{"save_path","下载根目录（新任务留空使用下载器默认目录）",""},{"interval_minutes","间隔（分钟，2–1440）","10"},{"concurrent","全部未完成任务并发上限","8"},{"reserve_gib","保留磁盘空间（GiB）","100"},{"capacity_gib","本任务容量上限（GiB）","500"},{"min_seeders","最低做种人数","2"},{"min_leechers","最低下载人数","3"},{"observe_hours","清理前观察小时（至少 6）","6"},{"low_upload_kib","低上传阈值（KiB/s）","32"},{"low_leechers","低需求人数阈值（0 关闭，须持续满 1 小时）","0"},{"min_seed_hours","最少累计做种小时（小时与分享率策略）","72"},{"min_ratio","最低分享率（与累计做种小时同时满足）","1.0"}};
   for(String[] x:values)fields.put(x[0],field(f,x[0],x[1],config.optString(x[0],x[2]),false,false));
   booleans.put("only_free",flag(f,"only_free","仅 FREE（默认）",config.optBoolean("only_free",true)));
   JSONArray promotions=config.optJSONArray("promotions");String promo=promotions==null?"FREE":promotions.toString().replace("[","").replace("]","").replace("\"","");
   fields.put("promotions",field(f,"promotions","促销白名单（逗号分隔，如 FREE,NORMAL,PERCENT_50,_2X_FREE）",promo,false,false));
   booleans.put("auto_delete",flag(f,"auto_delete","自动清理满足条件的自有任务",config.optBoolean("auto_delete",false)));
   booleans.put("delete_data",flag(f,"delete_data","同时删除这些任务的已验证文件",config.optBoolean("delete_data",false)));
   f.addView(a.text("新种子放入下载根目录下 nd-brush/任务编号/信息哈希 的专属目录。保种条件是你的明确声明，服务不会自动验证站点规则；只适用于此后新增的种子，旧任务的未知义务保持保护。",13,a.muted));
   f.addView(a.text("删除文件还须开启自动清理，并由 NAS 安装配置下载根目录的只读验证挂载；未配置时无法保存此开关。永久保护、身份变化、共享路径、文件变化或验证不通过都会阻止清理。未勾选删除文件时保留数据。",13,a.muted));
   f.addView(a.text("至少观察 6 小时，并取得约 1 小时上传样本；有效上传种继续保留。每轮最多清理 1 项，确认任务和文件状态并读取空间后再补种。已清理的差种须需求指标改善才可再入。非 FREE 还须当次证实 M-Team VIP 有效。",13,a.muted));
  }
  f.addView(a.button("保存配置",()->{try{
   JSONObject payload=a.json("name",a.value(name),"enabled",enabled.isChecked());if(old==null)payload.put("kind",kind);
   if(site!=null){if(sites.length()==0)throw new Exception("请先在站点配置中添加对应站点");payload.put("site_id",sites.getJSONObject(site.getSelectedItemPosition()).getString("id"));}
   if(engine!=null){if(downloaders.length()==0)throw new Exception("请先添加下载器");payload.put("downloader_id",downloaders.getJSONObject(engine.getSelectedItemPosition()).getString("id"));}
   for(Map.Entry<String,EditText> entry:secrets.entrySet())payload.put(entry.getKey(),entry.getValue().getText().toString());
   for(Map.Entry<String,EditText> entry:fields.entrySet()){
    String key=entry.getKey(),value=a.value(entry.getValue());
    if(key.equals("promotions")){JSONArray promos=new JSONArray();for(String part:value.split(","))if(!part.trim().isEmpty())promos.put(part.trim().toUpperCase(Locale.US));payload.put(key,promos);}
    else if(key.equals("save_path")){if(!value.isEmpty())payload.put(key,value);}
    else if(key.startsWith("window_")||key.endsWith("_contains")||key.equals("signin_url"))payload.put(key,value);
    else if(key.equals("min_ratio"))payload.put(key,Double.parseDouble(value));
    else payload.put(key,Integer.parseInt(value));
   }
   for(Map.Entry<String,CheckBox> entry:booleans.entrySet())payload.put(entry.getKey(),entry.getValue().isChecked());
   if(custom){payload.put("method",new String[]{"GET","POST"}[method.getSelectedItemPosition()]);payload.put("request_format",new String[]{"form","json","text"}[format.getSelectedItemPosition()]);if(payload.optString("success_contains").isEmpty())throw new Exception("请填写明确的签到成功标志");}
   if(brush){payload.put("retention_policy",new String[]{"unknown","no_obligation","seed_hours_ratio"}[retention.getSelectedItemPosition()]);if(payload.optBoolean("delete_data")&&!payload.optBoolean("auto_delete"))throw new Exception("删除文件须同时开启自动清理");}
   ArrayList<EditText> secretInputs=new ArrayList<>(secrets.values());
   if(old==null)createWithSecrets(payload,secretInputs);else a.read("保存后台任务…",()->a.api.request("PATCH",path(old),payload),saved->{clearSecrets(secretInputs);detail(saved.getJSONObject("item"));});
  }catch(NumberFormatException e){a.error("请检查数值字段：小时、人数和容量填写整数，分享率可填写小数。");}catch(Exception e){a.error(e.getMessage());}}));
 }
 void clearSecrets(List<EditText> inputs){for(EditText input:inputs)input.setText("");}
 void create(JSONObject payload,EditText cookie)throws Exception {createWithSecrets(payload,cookie==null?Collections.emptyList():Collections.singletonList(cookie));}
 void createWithSecrets(JSONObject payload,List<EditText> secrets)throws Exception {
  String key="create:"+a.signature("/automations",payload);String saved=tickets().getString(key,"");final String id=saved.isEmpty()?UUID.randomUUID().toString():saved;
  if(!tickets().edit().putString(key,id).commit())throw new Exception("无法保存创建编号，本次未提交");payload.put("request_id",id);
  a.read("保存后台任务（相同编号）…",()->a.api.request("POST","/automations",payload),result->{tickets().edit().remove(key).commit();clearSecrets(secrets);detail(result.getJSONObject("item"));});
 }
 void submitOriginal(JSONObject task,String key,String id,boolean dry){a.read("使用原编号登记后台运行…",()->a.api.request("POST",path(task)+"/run",a.json("request_id",id,"dry_run",dry)),j->checkRun(task,key,id));}
 SharedPreferences tickets(){return a.getSharedPreferences("automation-tickets",0);}
 String ticketKey(JSONObject task,boolean dry)throws Exception{return a.signature(path(task)+"/run",a.json("dry_run",dry));}
 void run(JSONObject task,boolean dry){if(a.busy)return;try{String key=ticketKey(task,dry),known=tickets().getString(key,"");if(!known.isEmpty()){checkRun(task,key,known);return;}String id=UUID.randomUUID().toString();if(!tickets().edit().putString(key,id).commit())throw new Exception("无法持久保存运行编号，未提交");JSONObject payload=a.json("request_id",id,"dry_run",dry);a.read("登记后台运行…",()->{try{return a.api.request("POST",path(task)+"/run",payload);}catch(Api.Failure e){if(e.status>=400&&e.status<500)tickets().edit().remove(key).commit();throw e;}},j->checkRun(task,key,id));}catch(Exception e){a.error(e.getMessage());}}
 void checkRun(JSONObject task,String key,String id){a.read("查询原运行记录（不重发）…",()->{try{return a.api.request("GET","/automation-runs/"+Api.segment(id),null);}catch(Api.Failure e){if(e.status==404)return a.json("not_found",true);throw e;}},j->{if(j.optBoolean("not_found")){boolean dry=key.equals(ticketKey(task,true));new AlertDialog.Builder(a).setTitle("服务端未找到这次运行").setMessage("可能请求尚未送达。确认后仅使用原编号重新提交，不会新建编号。编号："+id).setNegativeButton("取消",null).setPositiveButton("使用原编号重新提交",(d,w)->submitOriginal(task,key,id,dry)).show();return;}JSONObject run=j.getJSONObject("item");String s=run.optString("status");boolean terminal=!s.equals("queued")&&!s.equals("running");new AlertDialog.Builder(a).setTitle("后台运行："+state(s)).setMessage((run.optBoolean("dry_run")?"只读预演":"实际运行")+"\n编号："+id+"\n"+run.optJSONObject("result")).setNegativeButton("关闭",null).setPositiveButton(terminal?"确认结果（允许下次新运行）":"查看日志",(d,w)->{if(terminal)tickets().edit().remove(key).commit();logs(task);}).show();});}
 void logs(JSONObject task){a.screen("运行日志");a.body.addView(a.button("‹ 返回任务",()->detail(task)));a.body.addView(a.button("刷新日志",()->logs(task)));a.read("读取持久日志…",()->a.api.request("GET",path(task)+"/logs?limit=50",null),j->{JSONArray items=j.getJSONArray("items");if(items.length()==0)a.body.addView(a.text("暂无运行记录。",14,a.muted));for(int i=0;i<items.length();i++){JSONObject r=items.getJSONObject(i);LinearLayout c=a.card();c.addView(a.text(state(r.optString("status"))+" · "+(r.optBoolean("dry_run")?"预演":"实际")+" · "+time(r.optDouble("created_at")),15,a.ink));c.addView(a.text("编号："+r.optString("id")+"\n"+r.optJSONObject("result"),12,a.muted));a.body.addView(c);}});}
 void protections(JSONObject task){a.screen("归属与永久保护");a.body.addView(a.button("‹ 返回任务",()->detail(task)));a.body.addView(a.text("永久保护优先于清理规则；取消保护不能解除未知义务、身份或文件验证限制。删除文件仅在明确开启并完成验证时执行。",13,a.muted));EditText hash=a.input(a.body,"v1 信息哈希（40 位）","",false),reason=a.input(a.body,"保护原因","永久保护",false);a.body.addView(a.button("添加永久保护",()->{try{JSONObject p=a.json("info_hash",a.value(hash),"reason",a.value(reason));a.read("保存保护…",()->a.api.request("POST",path(task)+"/protections",p),j->protections(task));}catch(Exception e){a.error(e.getMessage());}}));a.read("读取归属与保护…",()->a.json("owned",a.api.request("GET",path(task)+"/owned",null).getJSONArray("items"),"protected",a.api.request("GET",path(task)+"/protections",null).getJSONArray("items")),j->{a.body.addView(a.text("永久保护",17,a.ink));JSONArray ps=j.getJSONArray("protected");for(int i=0;i<ps.length();i++){JSONObject p=ps.getJSONObject(i);a.body.addView(a.text(p.optString("info_hash")+"\n"+p.optString("reason"),12,a.muted));a.body.addView(a.button("取消此显式保护",()->new AlertDialog.Builder(a).setMessage("取消显式保护？其他保护规则仍然生效。").setNegativeButton("取消",null).setPositiveButton("确认",(d,w)->a.read("更新保护…",()->a.api.request("DELETE",path(task)+"/protections/"+Api.segment(p.optString("info_hash")),null),x->protections(task))).show()));}a.body.addView(a.text("本任务归属",17,a.ink));JSONArray os=j.getJSONArray("owned");for(int i=0;i<os.length();i++){JSONObject o=os.getJSONObject(i);a.body.addView(a.text(o.optString("info_hash")+" · "+o.optString("state")+"\n保种策略："+retentionLabel(o.optString("retention_policy","unknown"))+"\n专属目录："+o.optString("storage_path","旧任务未登记"),12,a.muted));}});}
}
