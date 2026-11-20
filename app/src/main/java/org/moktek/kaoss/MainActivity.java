package org.moktek.kaoss;
import android.app.Activity; import android.os.*; import android.content.*; import android.hardware.usb.*; import android.media.midi.*; import android.webkit.*; import org.json.*; import java.io.*;
public class MainActivity extends Activity {
 WebView web; MidiManager manager; MidiDevice device; MidiInputPort port; int generation=0; final Handler handler=new Handler(Looper.getMainLooper());
 @Override public void onCreate(Bundle b){super.onCreate(b); getWindow().addFlags(128); manager=(MidiManager)getSystemService(MIDI_SERVICE); web=new WebView(this); web.getSettings().setJavaScriptEnabled(true); web.getSettings().setDomStorageEnabled(true); web.getSettings().setAllowFileAccessFromFileURLs(false); web.getSettings().setAllowUniversalAccessFromFileURLs(false); web.addJavascriptInterface(new Bridge(),"Native"); setContentView(web); web.loadUrl("file:///android_asset/index.html"); }
 void event(String s){runOnUiThread(()->web.evaluateJavascript("nativeStatus("+JSONObject.quote(s)+")",null));}
 void close(){if(port!=null){try{port.close();}catch(IOException ignored){} port=null;} if(device!=null){try{device.close();}catch(IOException ignored){} device=null;}}
 class Bridge {
 @JavascriptInterface public String scan(){JSONArray a=new JSONArray(); if(manager!=null)for(MidiDeviceInfo d:manager.getDevices())for(MidiDeviceInfo.PortInfo p:d.getPorts())if(p.getType()==MidiDeviceInfo.PortInfo.TYPE_INPUT){JSONObject j=new JSONObject();try{j.put("id",d.getId());j.put("port",p.getPortNumber());j.put("name",String.valueOf(d.getProperties().getString(MidiDeviceInfo.PROPERTY_NAME))+" / "+p.getPortNumber());a.put(j);}catch(JSONException ignored){}} return a.toString();}
 @JavascriptInterface public String usb(){JSONArray a=new JSONArray(); UsbManager u=(UsbManager)getSystemService(USB_SERVICE);if(u!=null)for(UsbDevice d:u.getDeviceList().values())a.put(String.format("%04X:%04X %s",d.getVendorId(),d.getProductId(),d.getDeviceName()));return a.toString();}
 @JavascriptInterface public void connect(int id,int n){handler.post(()->{int g=++generation;close();if(manager==null){event("MIDI indisponible");return;}for(MidiDeviceInfo d:manager.getDevices())if(d.getId()==id){manager.openDevice(d,dev->{if(g!=generation){if(dev!=null)try{dev.close();}catch(IOException ignored){}return;}device=dev;port=dev==null?null:dev.openInputPort(n);event(port==null?"Échec ouverture MIDI":"MIDI connecté");},handler);return;}event("Périphérique absent");});}
 @JavascriptInterface public void disconnect(){handler.post(()->{generation++;close();event("Simulation");});}
 @JavascriptInterface public void send(int status,int a,int b,int length){if(status<128||status>239||a<0||a>127||b<0||b>127||length<2||length>3)return;handler.post(()->{if(port!=null)try{port.send(new byte[]{(byte)status,(byte)a,(byte)b},0,length);}catch(IOException e){close();event("Connexion MIDI perdue");}});}
 }
 @Override protected void onDestroy(){generation++;close();super.onDestroy();}
}
