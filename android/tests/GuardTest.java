import com.nasdownload.app.InstallGuard;
import com.nasdownload.app.UrlPolicy;
public class GuardTest {
 public static void main(String[] args)throws Exception {
  String root=exec("mktemp -d /tmp/nas-download-guard.XXXXXXXX",true).trim();
  String target=root+"/target";exec("mkdir "+UrlPolicy.quote(target),true);expect(target,true);
  exec("touch "+UrlPolicy.quote(target+"/unrelated"),true);expect(target,false);
  exec("printf nas-download-v1 > "+UrlPolicy.quote(target+"/.nas-download-install"),true);expect(target,true);
  exec("ln -s "+UrlPolicy.quote(target)+" "+UrlPolicy.quote(root+"/linked"),true);if(exec("if [ -L "+UrlPolicy.quote(root+"/linked")+" ]; then echo yes; fi",true).trim().equals("yes")){expect(root+"/linked",false);expect(root+"/linked/child",false);}else {if(!InstallGuard.command(target).contains("[ ! -L "))throw new AssertionError("missing symlink guard");System.out.println("Windows shell cannot create symlink fixture; symlink command contract checked");}
  expect(root+"/new/child",true);
  System.out.println("PASS guard: empty/new/own marker accepted; occupied refused; symlink guard contract verified");
 }
 static void expect(String dir,boolean pass)throws Exception{exec(InstallGuard.command(dir),pass);}
 static String exec(String command,boolean pass)throws Exception {java.io.File script=java.io.File.createTempFile("nas-guard-", ".sh");java.nio.file.Files.writeString(script.toPath(),"export PATH=/usr/bin:/bin\n"+command+"\n");Process p=new ProcessBuilder("C:/Program Files/Git/bin/bash.exe",script.getAbsolutePath()).redirectErrorStream(true).start();String out=new String(p.getInputStream().readAllBytes(),"UTF-8");int code=p.waitFor();if((code==0)!=pass)throw new AssertionError("guard exit "+code+": "+out);return out;}
}





