package com.nasdownload.app;
import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
final class TokenStore {
 private final SharedPreferences prefs;
 TokenStore(Context c){prefs=c.getSharedPreferences("session",0);}
 private SecretKey key() throws Exception {KeyStore k=KeyStore.getInstance("AndroidKeyStore");k.load(null);if(!k.containsAlias("nas-download-token")){KeyGenerator g=KeyGenerator.getInstance("AES","AndroidKeyStore");g.init(new KeyGenParameterSpec.Builder("nas-download-token",KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());g.generateKey();}return (SecretKey)k.getKey("nas-download-token",null);}
 void save(String base,String token)throws Exception{Cipher c=Cipher.getInstance("AES/GCM/NoPadding");c.init(Cipher.ENCRYPT_MODE,key());c.updateAAD(base.getBytes("UTF-8"));String enc=Base64.encodeToString(c.doFinal(token.getBytes("UTF-8")),Base64.NO_WRAP),iv=Base64.encodeToString(c.getIV(),Base64.NO_WRAP);if(!prefs.edit().putString("base",base).putString("token",enc).putString("iv",iv).commit())throw new Exception("无法保存会话");}
 String base(){return prefs.getString("base","");}
 String token(){try{if(base().isEmpty())return "";Cipher c=Cipher.getInstance("AES/GCM/NoPadding");c.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,Base64.decode(prefs.getString("iv",""),Base64.NO_WRAP)));c.updateAAD(base().getBytes("UTF-8"));return new String(c.doFinal(Base64.decode(prefs.getString("token",""),Base64.NO_WRAP)),"UTF-8");}catch(Exception e){clear();return "";}}
 void clear(){prefs.edit().clear().commit();}
}
