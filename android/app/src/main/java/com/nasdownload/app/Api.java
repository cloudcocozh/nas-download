package com.nasdownload.app;
import org.json.JSONObject;
import okhttp3.*;
import java.io.IOException;
final class Api { static final class Failure extends IOException { final int status; Failure(int status,String message){super(message);this.status=status;} }
 private final OkHttpClient client=new OkHttpClient.Builder().connectTimeout(15,java.util.concurrent.TimeUnit.SECONDS).readTimeout(45,java.util.concurrent.TimeUnit.SECONDS).followRedirects(false).followSslRedirects(false).retryOnConnectionFailure(false).build();
 String base="",token="";
 JSONObject request(String method,String path,JSONObject payload)throws Exception {
  String safe=UrlPolicy.normalize(base);Request.Builder b=new Request.Builder().url(safe+"/api/v1"+path).header("X-Nas-Request","1").header("Connection","close");if(!token.isEmpty())b.header("Authorization","Bearer "+token);
  b.method(method,method.equals("GET")?null:RequestBody.create(payload==null?"{}":payload.toString(),MediaType.get("application/json; charset=utf-8")));
  try(Response r=client.newCall(b.build()).execute()){String data=r.body()==null?"":r.body().string();JSONObject j;try{j=new JSONObject(data);}catch(Exception e){throw new IOException("服务返回了非 JSON 响应（"+r.code()+"）");}if(!r.isSuccessful()||!j.optBoolean("ok"))throw new Failure(r.code(),j.optString("error","请求失败 "+r.code()));return j;}
 }
 static String segment(String value){return android.net.Uri.encode(value);}
}

