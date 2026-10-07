package com.nasdownload.app;
import java.net.URI;
public final class UrlPolicy {
 public static String normalize(String raw) {
  try { URI u=new URI(raw.trim()); String h=u.getHost(); String scheme=u.getScheme();
   if(h==null||u.getUserInfo()!=null||u.getFragment()!=null||u.getQuery()!=null||(!"https".equals(scheme)&&!"http".equals(scheme)))throw new Exception();
   if("http".equals(scheme)&&!privateHost(h))throw new Exception();
   String p=u.getPath();if(p!=null&&!p.isEmpty()&&!p.equals("/"))throw new Exception();
   if(u.getPort()==0||u.getPort()>65535)throw new Exception();
   int port=u.getPort();if(port==443&&scheme.equals("https")||port==80&&scheme.equals("http"))port=-1;return scheme+"://"+h.toLowerCase(java.util.Locale.ROOT)+(port<0?"":":"+port);
  }catch(Exception e){throw new IllegalArgumentException("请输入 HTTPS 服务地址，或局域网或 Tailscale 数字 IP 的 HTTP 地址（不含路径、密码）。");}
 }
 public static boolean privateHost(String host) {
  if(!host.matches("[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+"))return false;
  String[] s=host.split("\\.");int[] n=new int[4];try{for(int i=0;i<4;i++){n[i]=Integer.parseInt(s[i]);if(n[i]>255||s[i].length()>1&&s[i].startsWith("0"))return false;}}catch(Exception e){return false;}
  return n[0]==100&&n[1]>=64&&n[1]<=127||n[0]==10||n[0]==127||n[0]==192&&n[1]==168||n[0]==172&&n[1]>=16&&n[1]<=31;
 }
 public static int servicePort(int port) {if(port<1024||port>65534)throw new IllegalArgumentException("服务端口须为 1024–65534");return port;}
 public static String installMode(int selection) {if(selection==0)return "bundled";if(selection==1)return "existing";throw new IllegalArgumentException("安装模式无效");}
 public static String quote(String value) {return "'"+value.replace("'","'\"'\"'")+"'";}
 public static String absoluteDir(String value) {
  if(value==null||!value.startsWith("/")||value.contains("\n")||value.contains("\r")||value.contains("\0"))throw new IllegalArgumentException("目录必须为非根目录的绝对路径");
  String normalized=value.endsWith("/")?value.substring(0,value.length()-1):value;
  if(normalized.isEmpty())throw new IllegalArgumentException("不能安装到根目录");
  for(String part:normalized.substring(1).split("/",-1))if(part.isEmpty()||part.equals(".")||part.equals(".."))throw new IllegalArgumentException("目录不能包含空段、. 或 ..");
  return normalized;
 }
}

