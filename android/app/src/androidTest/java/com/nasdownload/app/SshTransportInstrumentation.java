package com.nasdownload.app;
import android.app.Instrumentation;
import android.os.Bundle;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

/** Real JSch SSH + SFTP against a disposable host-side loopback fixture. */
public class SshTransportInstrumentation {
 Instrumentation test;
 SshTransportInstrumentation(Instrumentation t){test=t;}
 android.content.Context getTargetContext(){return test.getTargetContext();}
 String call(int port,SshInstaller.Confirm confirm)throws Exception{
  return SshInstaller.install(getTargetContext(),"127.0.0.1",port,"fixture","disposable-fixture-only","/fixture/install","127.0.0.1",17120,"/fixture/downloads","bundled",confirm,msg->{});
 }
 void fails(int port,SshInstaller.Confirm confirm,String expected)throws Exception{
  try{call(port,confirm);throw new AssertionError("unexpected SSH success at "+port);}catch(AssertionError e){throw e;}catch(Exception e){if(expected!=null&&!e.getMessage().contains(expected))throw new AssertionError("wrong failure at "+port+": "+e);}
 }
 void fill(android.view.View view,java.util.ArrayList<android.widget.EditText> fields){if(view instanceof android.widget.EditText)fields.add((android.widget.EditText)view);if(view instanceof android.view.ViewGroup){android.view.ViewGroup group=(android.view.ViewGroup)view;for(int n=0;n<group.getChildCount();n++)fill(group.getChildAt(n),fields);}}
 android.view.View control(android.view.View view,String label){if(view instanceof android.widget.TextView&&label.equals(((android.widget.TextView)view).getText().toString()))return view;if(view instanceof android.view.ViewGroup){android.view.ViewGroup group=(android.view.ViewGroup)view;for(int n=0;n<group.getChildCount();n++){android.view.View found=control(group.getChildAt(n),label);if(found!=null)return found;}}return null;}
 void navigation(int port)throws Exception{
  new TokenStore(getTargetContext()).clear();
  MainActivity activity=(MainActivity)test.startActivitySync(new android.content.Intent(getTargetContext(),MainActivity.class).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK));
  test.runOnMainSync(()->{activity.installForm();java.util.ArrayList<android.widget.EditText> fields=new java.util.ArrayList<>();fill(activity.body,fields);String[] values={"127.0.0.1",Integer.toString(port),"fixture","disposable-fixture-only","/fixture/install","127.0.0.1","17120","/fixture/downloads"};for(int n=0;n<values.length;n++)fields.get(n).setText(values[n]);for(int n=0;n<activity.body.getChildCount();n++)if(activity.body.getChildAt(n) instanceof android.widget.Spinner)((android.widget.Spinner)activity.body.getChildAt(n)).setSelection(0);control(activity.body,"验证并安装").performClick();control(activity.body,"‹ 返回").performClick();});
  long end=System.currentTimeMillis()+180000;boolean[] settled={false};while(System.currentTimeMillis()<end){test.runOnMainSync(()->settled[0]=!activity.busy);if(settled[0])break;Thread.sleep(100);}
  boolean[] unchanged={false};test.runOnMainSync(()->unchanged[0]=SmokeInstrumentation.contains(activity.getWindow().getDecorView(),"连接已有 NAS")&&activity.status.getVisibility()==android.view.View.GONE);test.runOnMainSync(activity::finish);
  if(!settled[0]||!unchanged[0])throw new AssertionError("late SSH installation replaced the navigated welcome page");
 }
 void run(){Bundle result=new Bundle();try{
  getTargetContext().getSharedPreferences("ssh-hosts",0).edit().clear().commit();
  AtomicInteger confirmations=new AtomicInteger();
  fails(22331,(h,fp)->{confirmations.incrementAndGet();return false;},null);
  if(confirmations.get()!=1||getTargetContext().getSharedPreferences("ssh-hosts",0).contains("127.0.0.1:22331"))throw new AssertionError("rejected key persisted");
  getTargetContext().getSharedPreferences("ssh-hosts",0).edit().putString("127.0.0.1:22332","SHA256:changed-fixture").commit();
  fails(22332,(h,fp)->{throw new AssertionError("changed host key offered for approval");},null);
  fails(22333,(h,fp)->true,null);
  fails(22334,(h,fp)->true,"occupied target refused");
  fails(22335,(h,fp)->true,"fixture extraction failed");
  fails(22336,(h,fp)->true,"fixture 安装失败");
  AtomicReference<Throwable> interrupted=new AtomicReference<>();
  java.util.concurrent.CountDownLatch installing=new java.util.concurrent.CountDownLatch(1);
  Thread worker=new Thread(()->{try{SshInstaller.install(getTargetContext(),"127.0.0.1",22337,"fixture","disposable-fixture-only","/fixture/install","127.0.0.1",17120,"/fixture/downloads","bundled",(h,fp)->true,msg->{if(msg.contains("安装产品"))installing.countDown();});interrupted.set(new AssertionError("interrupted installer completed"));}catch(Throwable t){interrupted.set(t);}});
  worker.start();if(!installing.await(180,java.util.concurrent.TimeUnit.SECONDS))throw new AssertionError("installer did not reach execution phase");Thread.sleep(200);worker.interrupt();worker.join(4000);
  if(worker.isAlive()||!(interrupted.get() instanceof InterruptedException))throw new AssertionError("installer interruption did not terminate: "+interrupted.get());
  String out=call(22330,(h,fp)->{if(!fp.startsWith("SHA256:"))throw new AssertionError("missing fingerprint");confirmations.incrementAndGet();return true;});
  InstallerResult parsed=InstallerResult.parse(out,"127.0.0.1",17120);
  if(!parsed.url.equals("http://127.0.0.1:17120")||!parsed.setupCode.equals("fixture-setup"))throw new AssertionError("installer output protocol lost: "+out);
  if(!out.contains("中文安装完成"))throw new AssertionError("SSH UTF-8 split reads corrupted native install output");
  call(22330,(h,fp)->{throw new AssertionError("saved host key asked again");});
  if(confirmations.get()!=2)throw new AssertionError("wrong host confirmation count");
  navigation(22330);navigation(22336);
  getTargetContext().getSharedPreferences("ssh-hosts",0).edit().clear().commit();
  result.putString("stream","PASS: real SSH host accept/reject/change, saved fingerprint reuse, password failure, pre-upload guard refusal, real SFTP asset/tar verification, install args/readiness/setup protocol, UTF-8 split reads, extraction/install errors, thread interruption and late installation navigation isolation\n");test.finish(0,result);
 }catch(Throwable t){result.putString("stream","FAIL: "+t+"\n");test.finish(1,result);}}
}
