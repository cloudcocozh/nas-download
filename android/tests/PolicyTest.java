import com.nasdownload.app.UrlPolicy;
public class PolicyTest {
 public static void main(String[] a) {
  for(int port:new int[]{1024,7120,65534})if(UrlPolicy.servicePort(port)!=port)throw new AssertionError();
  for(int port:new int[]{0,1,1023,65535,65536}){try{UrlPolicy.servicePort(port);throw new AssertionError("unsafe service port accepted");}catch(IllegalArgumentException expected){}}
  if(!UrlPolicy.installMode(0).equals("bundled")||!UrlPolicy.installMode(1).equals("existing"))throw new AssertionError("install modes");
  check("http://192.168.1.2:7120",true); check("http://127.0.0.1:7120",true); check("https://example.com",true);
  check("http://100.64.0.1:7120",true);check("http://100.127.255.254",true);check("http://100.63.255.255",false);check("http://100.128.0.1",false);check("http://100.064.0.1",false);check("http://example.com",false); check("http://8.8.8.8",false); check("http://192.168.1.2.evil.test",false); check("https://user:pass@example.com",false); check("file:///etc/passwd",false);
  if(!UrlPolicy.normalize("https://EXAMPLE.com:443/").equals("https://example.com"))throw new AssertionError("origin normalization");
  dir("/safe/install",true); dir("/safe/install/",true); dir("/",false);dir("/./",false);dir("//",false);dir("/safe//install",false);dir("/safe/../install",false);dir("/safe/./install",false);
  if (!UrlPolicy.quote("/a'b").equals("'/a'\"'\"'b'")) throw new AssertionError("shell quote");
 }
 static void dir(String s,boolean expected){try{UrlPolicy.absoluteDir(s);if(!expected)throw new AssertionError("unsafe dir accepted "+s);}catch(IllegalArgumentException e){if(expected)throw e;}}
 static void check(String s,boolean expected) {try {UrlPolicy.normalize(s);if(!expected)throw new AssertionError(s);}catch(IllegalArgumentException e){if(expected)throw e;}}
}


