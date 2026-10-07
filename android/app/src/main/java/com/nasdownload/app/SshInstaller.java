package com.nasdownload.app;
import android.content.Context;
import com.jcraft.jsch.*;
import java.io.*;
import java.security.MessageDigest;
import java.util.Base64;
final class SshInstaller {
 interface Confirm {boolean accept(String host,String fingerprint);}
 interface Progress {void status(String message);}
 static String install(Context context,String host,int port,String user,String password,String dir,String bind,int servicePort,String downloads,String mode,Confirm confirm,Progress progress)throws Exception {
  UrlPolicy.servicePort(servicePort);
  if(!host.matches("[A-Za-z0-9._:-]+")||host.startsWith("-"))throw new Exception("SSH 主机格式无效");dir=UrlPolicy.absoluteDir(dir);if(!downloads.isEmpty())downloads=UrlPolicy.absoluteDir(downloads);if(!mode.equals("existing")&&!mode.equals("bundled"))throw new Exception("安装模式无效");
  if(!bind.equals("0.0.0.0")&&!UrlPolicy.privateHost(bind))throw new Exception("绑定地址须为局域网数字 IP 或 0.0.0.0");
  JSch ssh=new JSch();String identity=host+":"+port;android.content.SharedPreferences prefs=context.getSharedPreferences("ssh-hosts",0);
  ssh.setHostKeyRepository(new HostKeyRepository(){
   public int check(String h,byte[] key){try{String fp="SHA256:"+Base64.getEncoder().withoutPadding().encodeToString(MessageDigest.getInstance("SHA-256").digest(key));String old=prefs.getString(identity,"");if(!old.isEmpty())return old.equals(fp)?OK:CHANGED;if(!confirm.accept(identity,fp))return NOT_INCLUDED;if(!prefs.edit().putString(identity,fp).commit())return NOT_INCLUDED;return OK;}catch(Exception e){return NOT_INCLUDED;}}
   public void add(HostKey k,UserInfo i){} public void remove(String h,String t){} public void remove(String h,String t,byte[] k){} public String getKnownHostsRepositoryID(){return "Android confirmed fingerprints";} public HostKey[] getHostKey(){return new HostKey[0];} public HostKey[] getHostKey(String h,String t){return new HostKey[0];}
  });
  Session session=ssh.getSession(user,host,port);session.setPassword(password);session.setConfig("StrictHostKeyChecking","yes");session.setConfig("PreferredAuthentications","password,keyboard-interactive");session.setTimeout(120000);
  String stage=null;boolean installed=false;
  try{progress.status("连接 SSH 并验证主机指纹…");session.connect(20000);progress.status("检查 Docker / Compose 与账户权限…");run(session,"command -v docker >/dev/null && docker compose version >/dev/null && docker info >/dev/null",90);
   progress.status("检查安装目录安全性…");run(session,InstallGuard.command(dir),30);
   stage=run(session,"umask 077; mktemp -d /tmp/nas-download-install.XXXXXXXX",30).trim();
   if(!stage.matches("/tmp/nas-download-install\\.[A-Za-z0-9]{8}"))throw new Exception("NAS 返回了无效的临时安装目录");
   run(session,"[ ! -L "+UrlPolicy.quote(stage)+" ] && [ -d "+UrlPolicy.quote(stage)+" ] && [ -O "+UrlPolicy.quote(stage)+" ]",30);
   progress.status("上传到私有临时目录…");ChannelSftp sftp=(ChannelSftp)session.openChannel("sftp");sftp.connect(15000);try(InputStream input=context.getAssets().open("installer.bundle")){long total=assetSize(context);sftp.put(input,stage+"/installer.tar.gz",new SftpProgressMonitor(){long sent,last;public void init(int op,String src,String dest,long max){}public boolean count(long count){sent+=count;long now=System.currentTimeMillis();if(now-last>=1000){last=now;progress.status("上传安装包… "+(sent*100/Math.max(1,total))+"%");}return true;}public void end(){progress.status("上传完成，解压安装包…");}},ChannelSftp.OVERWRITE);}finally{sftp.disconnect();}
   run(session,"tar -xzf "+UrlPolicy.quote(stage+"/installer.tar.gz")+" -C "+UrlPolicy.quote(stage),300);
   run(session,InstallGuard.command(dir),30);
   progress.status("安装产品并验证下载引擎…");String result=run(session,"cd "+UrlPolicy.quote(stage)+" && sh install.sh --dir "+UrlPolicy.quote(dir)+" --port "+servicePort+" --bind "+UrlPolicy.quote(bind)+" --mode "+UrlPolicy.quote(mode)+(downloads.isEmpty()?"":" --downloads "+UrlPolicy.quote(downloads)),1800);installed=true;return result;  }finally{if(installed&&stage!=null&&stage.matches("/tmp/nas-download-install\\.[A-Za-z0-9]{8}")){try{run(session,"[ ! -L "+UrlPolicy.quote(stage)+" ] && [ -d "+UrlPolicy.quote(stage)+" ] && [ -O "+UrlPolicy.quote(stage)+" ] && rm -rf -- "+UrlPolicy.quote(stage),30);}catch(Exception cleanup){progress.status("安装完成；临时安装包未能清理。");}}session.disconnect();}
 }
 private static long assetSize(Context context)throws IOException {try(InputStream in=context.getAssets().open("installer.bundle")){byte[] buffer=new byte[65536];long size=0;int count;while((count=in.read(buffer))!=-1)size+=count;return size;}}
 private static String run(Session s,String cmd,int seconds)throws Exception {ChannelExec c=(ChannelExec)s.openChannel("exec");c.setCommand(cmd);c.setInputStream(null);ByteArrayOutputStream err=new ByteArrayOutputStream();c.setErrStream(err);InputStream in=c.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] b=new byte[4096];long end=System.currentTimeMillis()+seconds*1000L;try{c.connect(15000);while(true){while(in.available()>0){int n=in.read(b);if(n<0)break;if(out.size()<100000)out.write(b,0,Math.min(n,100000-out.size()));}if(c.isClosed()&&in.available()==0)break;if(System.currentTimeMillis()>end)throw new Exception("安装步骤超时。请检查 NAS 中安装目录的日志，勿重复创建服务。");Thread.sleep(100);}if(c.getExitStatus()!=0)throw new Exception("NAS 安装步骤失败（"+c.getExitStatus()+"）："+err.toString("UTF-8"));return out.toString("UTF-8");}finally{c.disconnect();}}
}



