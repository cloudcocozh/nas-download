package com.nasdownload.app;
import android.app.Instrumentation;
import android.content.Intent;
import android.view.*;
import android.widget.*;
import org.json.*;
import java.net.*;
import java.io.*;
import java.util.*;
import java.util.concurrent.atomic.*;

final class AutomationFixture {
 static void run(Instrumentation test)throws Exception {
  ServerSocket server=new ServerSocket(0,20,InetAddress.getByName("127.0.0.1"));
  AtomicInteger posts=new AtomicInteger(),stops=new AtomicInteger(),lookups=new AtomicInteger();
  AtomicBoolean slow=new AtomicBoolean(),dropCreate=new AtomicBoolean();AtomicReference<String> firstCreate=new AtomicReference<>();Map<String,JSONObject> runs=new java.util.concurrent.ConcurrentHashMap<>();AtomicReference<JSONObject> saved=new AtomicReference<>();
  JSONObject task=new JSONObject().put("id","auto-fixture").put("name","Automation Fixture").put("kind","hdfans_signin").put("enabled",false).put("has_cookie",true).put("window_start","08:00").put("window_end","10:00").put("last_status","idle");
  Thread thread=new Thread(()->{while(!server.isClosed())try(Socket socket=server.accept()){
   InputStream reader=socket.getInputStream();String line=readLine(reader),h;int length=0;while((h=readLine(reader))!=null&&!h.isEmpty())if(h.toLowerCase().startsWith("content-length:"))length=Integer.parseInt(h.substring(15).trim());byte[] bytes=new byte[length];int got=0;while(got<length){int n=reader.read(bytes,got,length-got);if(n<0)break;got+=n;}JSONObject payload=length==0?new JSONObject():new JSONObject(new String(bytes,"UTF-8"));JSONObject response=new JSONObject().put("ok",true);int status=200;
   if(line.startsWith("POST /api/v1/automations ")||line.startsWith("PATCH /api/v1/automations/auto-fixture ")){saved.set(payload);task.put("name",payload.optString("name")).put("enabled",payload.optBoolean("enabled"));response.put("item",task);if(line.startsWith("POST ")&&dropCreate.getAndSet(false)){firstCreate.set(payload.getString("request_id"));continue;}}
   else if(line.startsWith("POST ")&&line.contains("/run ")){posts.incrementAndGet();String id=payload.getString("request_id");runs.put(id,new JSONObject().put("id",id).put("status","running").put("dry_run",payload.getBoolean("dry_run")).put("result",new JSONObject().put("reason","fixture retained")));continue;}
   else if(line.contains("GET /api/v1/automation-runs/")){lookups.incrementAndGet();String id=line.split(" ")[1].substring("/api/v1/automation-runs/".length());if(runs.containsKey(id))response.put("item",runs.get(id));else{status=404;response.put("ok",false).put("error","not found");}}
   else if(line.contains("/stop ")){stops.incrementAndGet();task.put("enabled",false).put("last_status","cancelled");for(JSONObject r:runs.values())r.put("status","cancelled");response.put("item",task);}
   else if(line.contains("/logs?")){if(slow.get())Thread.sleep(600);JSONArray items=new JSONArray();for(JSONObject r:runs.values())items.put(r);response.put("items",items);}
   else if(line.contains("/automations "))response.put("items",new JSONArray().put(task));
   else if(line.contains("/downloaders"))response.put("items",new JSONArray().put(new JSONObject().put("id","fixture-engine").put("name","Fixture engine")));
   else if(line.contains("/tasks?"))response.put("items",new JSONArray()).put("summary",new JSONObject()).put("total",0);
   else if(line.contains("/sites"))response.put("items",new JSONArray().put(new JSONObject().put("id","fixture-site").put("name","Fixture site").put("type","mteam")));
   byte[] data=response.toString().getBytes("UTF-8");socket.getOutputStream().write(("HTTP/1.1 "+status+" OK\r\nContent-Type: application/json\r\nContent-Length: "+data.length+"\r\nConnection: close\r\n\r\n").getBytes("UTF-8"));socket.getOutputStream().write(data);
  }catch(Exception e){if(!server.isClosed())e.printStackTrace();}});thread.start();
  TokenStore store=new TokenStore(test.getTargetContext());store.save("http://127.0.0.1:"+server.getLocalPort(),"automation-fixture-token");MainActivity a=null;
  try{
   a=(MainActivity)test.startActivitySync(new Intent(test.getTargetContext(),MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));idle(test,a);final MainActivity first=a;AutomationUi ui=new AutomationUi(a);
   test.runOnMainSync(ui::list);idle(test,a);assertText(test,a,"Automation Fixture");
   test.runOnMainSync(()->ui.renderForm(null,"hdfans_signin",new JSONArray(),new JSONArray()));final boolean[] disabled={false};test.runOnMainSync(()->disabled[0]=!findCheck(first.body).isChecked());if(!disabled[0])throw new AssertionError("new task auto-enabled");
   test.runOnMainSync(()->{ArrayList<EditText> inputs=new ArrayList<>();collect(first.body,inputs);inputs.get(0).setText("Automation Fixture");inputs.get(1).setText("private-fixture-cookie");findButton(first.body,"保存配置").performClick();});idle(test,a);if(saved.get()==null||saved.get().optBoolean("enabled")||!saved.get().optString("cookie").equals("private-fixture-cookie"))throw new AssertionError("create defaults/config missing");
   test.runOnMainSync(()->ui.renderForm(task,"hdfans_signin",new JSONArray(),new JSONArray()));test.runOnMainSync(()->findButton(first.body,"保存配置").performClick());idle(test,a);if(!saved.get().has("cookie")||!saved.get().getString("cookie").isEmpty())throw new AssertionError("empty cookie preservation contract");if(!test.getTargetContext().getSharedPreferences("automation-tickets",0).getAll().isEmpty())throw new AssertionError("config wrote ticket");
   verifyV12Forms(test,first,ui,saved);
   JSONObject creating=new JSONObject().put("kind","http_signin").put("name","Uncertain create fixture").put("signin_url","https://fixture.invalid/signin").put("success_contains","signed").put("cookie","fixture-secret-not-persisted").put("headers_json","{\"X-Fixture\":\"fixture-header-not-persisted\"}").put("request_body","{\"token\":\"fixture-body-not-persisted\"}").put("enabled",false);
   dropCreate.set(true);test.runOnMainSync(()->{try{ui.create(new JSONObject(creating.toString()),null);}catch(Exception e){throw new RuntimeException(e);}});idle(test,a);
   String pending=ui.tickets().getAll().toString();for(String secret:new String[]{"fixture-secret-not-persisted","fixture-header-not-persisted","fixture-body-not-persisted"})if(pending.contains(secret))throw new AssertionError("pending create persisted secret");
   test.runOnMainSync(()->{try{ui.create(new JSONObject(creating.toString()),null);}catch(Exception e){throw new RuntimeException(e);}});idle(test,a);if(firstCreate.get()==null||!firstCreate.get().equals(saved.get().optString("request_id")))throw new AssertionError("uncertain create changed UUID");
   test.runOnMainSync(()->ui.run(task,true));idle(test,a);if(posts.get()!=1||test.getTargetContext().getSharedPreferences("automation-tickets",0).getAll().size()!=1)throw new AssertionError("run ticket missing before uncertain result posts="+posts.get()+" tickets="+test.getTargetContext().getSharedPreferences("automation-tickets",0).getAll().size());
   test.runOnMainSync(first::finish);a=(MainActivity)test.startActivitySync(new Intent(test.getTargetContext(),MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));idle(test,a);AutomationUi again=new AutomationUi(a);final MainActivity current=a;
   test.runOnMainSync(()->again.run(task,true));idle(test,a);if(posts.get()!=1||lookups.get()!=1)throw new AssertionError("uncertain run replayed after app restart");test.sendKeyDownUpSync(KeyEvent.KEYCODE_BACK);
   test.runOnMainSync(()->again.stop(task));idle(test,a);if(stops.get()!=1)throw new AssertionError("stop not sent");assertText(test,a,"已停用");
   test.runOnMainSync(()->again.logs(task));idle(test,a);assertText(test,a,"fixture retained");assertText(test,a,"已停止");
   String missing=UUID.randomUUID().toString(),key=again.ticketKey(task,true);again.tickets().edit().putString(key,missing).commit();int beforeRetry=posts.get();
   test.runOnMainSync(()->again.run(task,true));idle(test,a);if(posts.get()!=beforeRetry)throw new AssertionError("404 auto-replayed without confirmation");test.sendKeyDownUpSync(KeyEvent.KEYCODE_BACK);
   test.runOnMainSync(()->again.submitOriginal(task,key,missing,true));idle(test,a);if(posts.get()!=beforeRetry+1||!runs.containsKey(missing))throw new AssertionError("404 retry did not use original UUID");
   slow.set(true);test.runOnMainSync(()->{again.logs(task);current.welcome();});idle(test,a);assertText(test,a,"连接已有 NAS");final boolean[] stale={false};test.runOnMainSync(()->stale[0]=SmokeInstrumentation.contains(current.getWindow().getDecorView(),"fixture retained"));if(stale[0])throw new AssertionError("late logs changed new page");
   if(test.getTargetContext().getSharedPreferences("automation-tickets",0).getAll().toString().contains("private-fixture-cookie"))throw new AssertionError("cookie persisted on phone");
  }finally{if(a!=null){final MainActivity end=a;test.runOnMainSync(end::finish);}server.close();store.clear();test.getTargetContext().getSharedPreferences("automation-tickets",0).edit().clear().commit();}
 }
 static void verifyV12Forms(Instrumentation test,MainActivity activity,AutomationUi ui,AtomicReference<JSONObject> saved)throws Exception {
  test.runOnMainSync(()->ui.renderForm(null,"http_signin",new JSONArray(),new JSONArray()));
  capture(test,activity,"automation-120-http.png");
  test.runOnMainSync(()->{
   field(activity.body,"signin_url").setText("https://fixture.invalid/attendance");
   field(activity.body,"success_contains").setText("signed successfully");
   field(activity.body,"already_contains").setText("already signed");
   field(activity.body,"failure_contains").setText("login required");
   field(activity.body,"cookie").setText("fixture-http-cookie");
   field(activity.body,"headers_json").setText("{\"X-Fixture\":\"fixture-header-secret\"}");
   field(activity.body,"request_body").setText("{\"token\":\"fixture-body-secret\"}");
   ((Spinner)activity.body.findViewWithTag("method")).setSelection(1);
   ((Spinner)activity.body.findViewWithTag("request_format")).setSelection(1);
   for(String key:new String[]{"cookie","headers_json","request_body"})if(field(activity.body,key).isSaveEnabled())throw new AssertionError("secret allows view state persistence");
   findButton(activity.body,"保存配置").performClick();
  });idle(test,activity);
  JSONObject http=saved.get();
  if(!http.optString("kind").equals("http_signin")||http.has("site_id")||!http.optString("method").equals("POST")||!http.optString("request_format").equals("json")||http.optInt("expected_status")!=200||!http.optString("success_contains").equals("signed successfully")||!http.optString("request_body").contains("fixture-body-secret"))throw new AssertionError("HTTP signin fields not saved");
  JSONObject existing=new JSONObject(http.toString()).put("id","auto-fixture").put("has_cookie",true).put("has_headers_json",true).put("has_request_body",true);
  existing.remove("cookie");existing.remove("headers_json");existing.remove("request_body");
  test.runOnMainSync(()->ui.renderForm(existing,"http_signin",new JSONArray(),new JSONArray()));
  test.runOnMainSync(()->findButton(activity.body,"保存配置").performClick());idle(test,activity);
  for(String key:new String[]{"cookie","headers_json","request_body"})if(!saved.get().has(key)||!saved.get().optString(key).isEmpty())throw new AssertionError("HTTP empty secret preservation contract");
  JSONArray sites=new JSONArray().put(new JSONObject().put("id","fixture-site").put("name","Fixture site").put("type","mteam"));
  JSONArray engines=new JSONArray().put(new JSONObject().put("id","fixture-engine").put("name","Fixture engine"));
  test.runOnMainSync(()->ui.renderForm(null,"brush",sites,engines));
  test.waitForIdleSync();test.runOnMainSync(()->activity.scroll.fullScroll(View.FOCUS_DOWN));capture(test,activity,"automation-120-brush.png");
  test.runOnMainSync(()->{
   if(((CheckBox)activity.body.findViewWithTag("auto_delete")).isChecked()||((CheckBox)activity.body.findViewWithTag("delete_data")).isChecked())throw new AssertionError("cleanup default enabled");
   ((Spinner)activity.body.findViewWithTag("retention_policy")).setSelection(2);
   field(activity.body,"min_seed_hours").setText("48");field(activity.body,"min_ratio").setText("1.5");field(activity.body,"low_leechers").setText("2");
   ((CheckBox)activity.body.findViewWithTag("auto_delete")).setChecked(true);((CheckBox)activity.body.findViewWithTag("delete_data")).setChecked(true);
   findButton(activity.body,"保存配置").performClick();
  });idle(test,activity);JSONObject brush=saved.get();
  if(!brush.optString("retention_policy").equals("seed_hours_ratio")||brush.optInt("min_seed_hours")!=48||brush.optDouble("min_ratio")!=1.5||brush.optInt("low_leechers")!=2||!brush.optBoolean("auto_delete")||!brush.optBoolean("delete_data"))throw new AssertionError("brush 1.2 fields not saved");
  String persistent=activity.getSharedPreferences("automation-tickets",0).getAll().toString();
  for(String secret:new String[]{"fixture-http-cookie","fixture-header-secret","fixture-body-secret"})if(persistent.contains(secret))throw new AssertionError("HTTP secret persisted on phone");
 }
 static EditText field(ViewGroup group,String key){EditText result=group.findViewWithTag(key);if(result==null)throw new AssertionError("missing form field "+key);return result;}
 static String readLine(InputStream input)throws IOException{ByteArrayOutputStream out=new ByteArrayOutputStream();int ch;while((ch=input.read())!=-1&&ch!='\n')if(ch!='\r')out.write(ch);return ch==-1&&out.size()==0?null:out.toString("US-ASCII");}
 static void capture(Instrumentation test,MainActivity activity,String name)throws Exception{test.waitForIdleSync();android.graphics.Bitmap shot=test.getUiAutomation().takeScreenshot();if(shot==null)throw new AssertionError("screenshot unavailable");try(FileOutputStream out=new FileOutputStream(new File(activity.getExternalFilesDir(null),name))){shot.compress(android.graphics.Bitmap.CompressFormat.PNG,100,out);}finally{shot.recycle();}}
 static void idle(Instrumentation test,MainActivity a)throws Exception{long end=System.currentTimeMillis()+15000;while(System.currentTimeMillis()<end){boolean[] idle={false};test.runOnMainSync(()->idle[0]=!a.busy);if(idle[0]){test.waitForIdleSync();return;}Thread.sleep(50);}throw new AssertionError("automation request did not settle");}
 static void assertText(Instrumentation test,MainActivity a,String text){boolean[] yes={false};test.runOnMainSync(()->yes[0]=SmokeInstrumentation.contains(a.getWindow().getDecorView(),text));if(!yes[0])throw new AssertionError("missing automation UI "+text);}
 static Button findButton(View v,String label){if(v instanceof Button&&((Button)v).getText().toString().equals(label))return (Button)v;if(v instanceof ViewGroup){ViewGroup g=(ViewGroup)v;for(int i=0;i<g.getChildCount();i++){Button b=findButton(g.getChildAt(i),label);if(b!=null)return b;}}return null;}
 static CheckBox findCheck(View v){if(v instanceof CheckBox)return (CheckBox)v;if(v instanceof ViewGroup){ViewGroup g=(ViewGroup)v;for(int i=0;i<g.getChildCount();i++){CheckBox b=findCheck(g.getChildAt(i));if(b!=null)return b;}}return null;}
 static void collect(View v,ArrayList<EditText> out){if(v instanceof EditText)out.add((EditText)v);else if(v instanceof ViewGroup){ViewGroup g=(ViewGroup)v;for(int i=0;i<g.getChildCount();i++)collect(g.getChildAt(i),out);}}
}
