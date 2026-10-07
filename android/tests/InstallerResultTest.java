import com.nasdownload.app.InstallerResult;
public class InstallerResultTest {
 public static void main(String[] args) {
  InstallerResult r=InstallerResult.parse("Build log\r\nNAS_DOWNLOAD_READY=http://<host>:7130\r\nNAS_DOWNLOAD_SETUP_CODE=abc123\r\n","100.70.1.2",7130);
  if(!r.url.equals("http://100.70.1.2:7130")||!r.setupCode.equals("abc123"))throw new AssertionError("CRLF result");
  if(!InstallerResult.parse("NAS_DOWNLOAD_READY=http://0.0.0.0:7130\n","192.168.1.2",7130).setupCode.isEmpty())throw new AssertionError("existing install");
  try{InstallerResult.parse("not ready","192.168.1.2",7130);throw new AssertionError("missing readiness");}catch(IllegalArgumentException expected){}
 }
}
