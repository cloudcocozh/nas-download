package com.nasdownload.app;
public final class InstallerResult {
 public final String url,setupCode;
 private InstallerResult(String u,String c){url=u;setupCode=c;}
 public static InstallerResult parse(String output,String host,int port) {
  String url="",code="";
  for(String line:output.split("\r?\n")) {
   if(line.startsWith("NAS_DOWNLOAD_READY="))url=line.substring("NAS_DOWNLOAD_READY=".length()).trim();
   if(line.startsWith("NAS_DOWNLOAD_SETUP_CODE="))code=line.substring("NAS_DOWNLOAD_SETUP_CODE=".length()).trim();
  }
  if(url.isEmpty())throw new IllegalArgumentException("安装未返回就绪确认，请检查 NAS 安装日志，避免重复安装。");
  url=url.replace("<host>",host).replace("0.0.0.0",host);
  return new InstallerResult(UrlPolicy.normalize(url),code);
 }
}
