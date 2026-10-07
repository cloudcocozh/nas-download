package com.nasdownload.app;
import android.app.Instrumentation;
import android.os.Bundle;
import java.io.*;
import java.net.*;

/** HTTP/1.0 does not promise persistent connections; delay FIN to expose reuse races. */
final class HttpTransportFixture {
 static void run(Instrumentation test){Bundle result=new Bundle();ServerSocket server=null;try{
  server=new ServerSocket(0,20,InetAddress.getByName("127.0.0.1"));final ServerSocket socket=server;
  Thread serve=new Thread(()->{while(!socket.isClosed())try{Socket client=socket.accept();new Thread(()->{try(Socket c=client){BufferedReader reader=new BufferedReader(new InputStreamReader(c.getInputStream(),"UTF-8"));reader.readLine();int length=0;String line;while((line=reader.readLine())!=null&&!line.isEmpty())if(line.toLowerCase().startsWith("content-length:"))length=Integer.parseInt(line.substring(15).trim());for(int n=0;n<length;n++)reader.read();byte[] body="{\"ok\":true}".getBytes("UTF-8");OutputStream output=c.getOutputStream();output.write(("HTTP/1.0 200 OK\r\nContent-Type: application/json\r\nContent-Length: "+body.length+"\r\n\r\n").getBytes("UTF-8"));output.write(body);output.flush();Thread.sleep(250);}catch(Exception ignored){}}).start();}catch(Exception ignored){}});serve.setDaemon(true);serve.start();
  Api api=new Api();api.base="http://127.0.0.1:"+server.getLocalPort();
  for(int n=0;n<3;n++){api.request("POST","/login",new org.json.JSONObject().put("fixture",true));api.request("GET","/downloaders",null);api.request("GET","/tasks",null);}
  result.putString("stream","PASS: sequential native POST/GET requests with valid HTTP/1.0 close semantics and delayed FIN\n");test.finish(0,result);
 }catch(Throwable error){result.putString("stream","FAIL: sequential native HTTP/1.0 transport "+error.getClass().getSimpleName()+"\n");test.finish(1,result);}finally{if(server!=null)try{server.close();}catch(Exception ignored){}}}
}
