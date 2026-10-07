package com.nasdownload.app;
import android.app.Instrumentation;
import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.view.ViewGroup;
import android.widget.EditText;
import android.widget.TextView;
import android.view.accessibility.AccessibilityNodeInfo;
import java.io.*;
import java.util.ArrayList;
import org.json.*;

/** Uses a root-provided disposable QA config; no credentials embedded in APKs. */
final class LiveQaInstrumentation {
 final Instrumentation test; MainActivity activity; JSONObject config; String phase="config";
 LiveQaInstrumentation(Instrumentation i){test=i;}
 void idle()throws Exception{long end=System.currentTimeMillis()+20000;while(System.currentTimeMillis()<end){boolean[] ready={false};test.runOnMainSync(()->ready[0]=!activity.busy);if(ready[0]){test.waitForIdleSync();return;}Thread.sleep(80);}throw new AssertionError("native request did not settle");}
 static void fields(View v,ArrayList<EditText> out){if(v instanceof EditText)out.add((EditText)v);if(v instanceof ViewGroup){ViewGroup g=(ViewGroup)v;for(int n=0;n<g.getChildCount();n++)fields(g.getChildAt(n),out);}}
 static boolean click(AccessibilityNodeInfo n,String value){if(n==null)return false;if(n.getText()!=null&&value.equals(n.getText().toString()))return n.performAction(AccessibilityNodeInfo.ACTION_CLICK);for(int i=0;i<n.getChildCount();i++)if(click(n.getChild(i),value))return true;return false;}
 void tap(String value)throws Exception{long end=System.currentTimeMillis()+8000;while(System.currentTimeMillis()<end){if(click(test.getUiAutomation().getRootInActiveWindow(),value)){test.waitForIdleSync();return;}Thread.sleep(80);}throw new AssertionError("native control missing: "+value);}
 void text(String value)throws Exception{long end=System.currentTimeMillis()+20000;while(System.currentTimeMillis()<end){boolean[] ready={false};test.runOnMainSync(()->ready[0]=!activity.busy&&SmokeInstrumentation.contains(activity.getWindow().getDecorView(),value));if(ready[0])return;Thread.sleep(100);}throw new AssertionError("native task text missing");}
 JSONObject findTask(boolean expected)throws Exception{
  long end=System.currentTimeMillis()+15000;
  while(System.currentTimeMillis()<end){JSONArray items=activity.api.request("GET","/tasks?downloader_id="+Api.segment(config.getString("downloader_id"))+"&limit=100&offset=0",null).getJSONArray("items");JSONObject found=null;for(int n=0;n<items.length();n++){JSONObject item=items.getJSONObject(n);if(config.getString("task_name").equals(item.optString("name")))found=item;}if(expected&&found!=null)return found;if(!expected&&found==null)return null;Thread.sleep(150);}
  throw new AssertionError(expected?"QA task not returned by downloader":"task remained after native delete");
 }
 void state(String expected)throws Exception{long end=System.currentTimeMillis()+15000;while(System.currentTimeMillis()<end){JSONObject item=findTask(true);if(expected.equals(item.optString("state")))return;Thread.sleep(150);}throw new AssertionError("downloader state did not change to "+expected);}
 void receipt()throws Exception{idle();tap("确定");idle();}
 void run(Bundle arguments){Bundle result=new Bundle();try{
  File file=new File(test.getTargetContext().getExternalFilesDir(null),"qa-config.json");
  try(InputStream input=new FileInputStream(file);ByteArrayOutputStream bytes=new ByteArrayOutputStream()){byte[] chunk=new byte[4096];int n;while((n=input.read(chunk))>=0)bytes.write(chunk,0,n);config=new JSONObject(bytes.toString("UTF-8"));}
  if(!config.optBoolean("disposable_qa"))throw new AssertionError("QA config must explicitly declare disposable_qa");
  TokenStore store=new TokenStore(test.getTargetContext());store.clear();test.getTargetContext().getSharedPreferences("operations",0).edit().clear().commit();
  phase="native login";activity=(MainActivity)test.startActivitySync(new Intent(test.getTargetContext(),MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
  test.runOnMainSync(()->{activity.connect(false);ArrayList<EditText> fields=new ArrayList<>();fields(activity.body,fields);fields.get(0).setText(config.optString("base"));fields.get(1).setText(config.optString("username"));fields.get(2).setText(config.optString("password"));});
  tap("连接");text("全部下载器");if(activity.api.token.isEmpty())throw new AssertionError("native login did not establish session");
  phase="native add";
  test.runOnMainSync(()->{try{JSONObject payload=activity.json("downloader_id",config.getString("downloader_id"),"torrent_base64",config.getString("torrent_base64"),"paused",true);if(config.has("save_path"))payload.put("save_path",config.getString("save_path"));activity.mutate("/tasks/add",payload);}catch(Exception e){throw new RuntimeException(e);}});
  receipt();text(config.getString("task_name"));JSONObject item=findTask(true);state("paused");
  try(FileOutputStream shot=new FileOutputStream(new File(test.getTargetContext().getExternalFilesDir(null),"live-qa-tasks.png"))){test.getUiAutomation().takeScreenshot().compress(android.graphics.Bitmap.CompressFormat.PNG,100,shot);}
  phase="native details/resume";final JSONObject resumeItem=item;test.runOnMainSync(()->activity.detail(resumeItem));idle();tap("继续");receipt();test.sendKeyDownUpSync(android.view.KeyEvent.KEYCODE_BACK);
  long end=System.currentTimeMillis()+15000;while(System.currentTimeMillis()<end&&"paused".equals(findTask(true).optString("state")))Thread.sleep(100);if("paused".equals(findTask(true).optString("state")))throw new AssertionError("native resume did not change real downloader state");
  phase="native pause";item=findTask(true);final JSONObject pauseItem=item;test.runOnMainSync(()->activity.action(pauseItem,"pause",false));receipt();state("paused");
  phase="native activity restart";test.runOnMainSync(activity::finish);activity=(MainActivity)test.startActivitySync(new Intent(test.getTargetContext(),MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));text(config.getString("task_name"));if(activity.api.token.isEmpty())throw new AssertionError("encrypted token missing after restart");
  phase="native delete confirmation";item=findTask(true);final JSONObject deleteItem=item;test.runOnMainSync(()->activity.deleteTask(deleteItem));tap("删除");receipt();findTask(false);
  phase="cleanup";activity.api.request("POST","/logout",new JSONObject());store.clear();test.runOnMainSync(activity::finish);file.delete();
  result.putString("stream","PASS: native UI login to independent QA service, encrypted session restart, native torrent add and task rendering, real downloader paused/resumed/paused state, detail resume control, delete confirmation with delete_data=false, logout and private config cleanup\n");test.finish(0,result);
 }catch(Throwable error){String[] state={""};if(activity!=null)test.runOnMainSync(()->state[0]=" busy="+activity.busy+" authenticated="+!activity.api.token.isEmpty()+" allLabel="+SmokeInstrumentation.contains(activity.getWindow().getDecorView(),"全部下载器")+" downloaderRows="+(activity.select==null||activity.select.getAdapter()==null?-1:activity.select.getAdapter().getCount())+" streamEnded="+activity.status.getText().toString().contains("unexpected end of stream"));result.putString("stream","FAIL: private native QA phase="+phase+" type="+error.getClass().getSimpleName()+state[0]+" (credentials and endpoint withheld)\n");test.finish(1,result);}}
}
