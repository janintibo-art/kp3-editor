package org.moktek.kaoss

import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.media.midi.*
import android.hardware.usb.UsbManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.*
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import android.graphics.BitmapFactory
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.Job
import org.json.JSONArray
import org.json.JSONObject

private val Red = Color(0xffff493e)
private val Ink = Color(0xff100f10)
private val Panel = Color(0xff24201e)
private val Bone = Color(0xffe9dac2)
private data class Motion(val t:Long,val x:Int,val y:Int,val gate:Int)
private data class Endpoint(val info:MidiDeviceInfo,val port:Int,val label:String)
open class NativeActivity : ComponentActivity() {
 private val midi by lazy { getSystemService(MIDI_SERVICE) as? MidiManager }
 private val handler = Handler(Looper.getMainLooper())
 private var device:MidiDevice?=null
 private var port:MidiInputPort?=null
 private var generation=0
 private var status by mutableStateOf("SIMULATION")
 private var channel by mutableIntStateOf(1)
 private var endpoints by mutableStateOf(emptyList<Endpoint>())
 private val logs=mutableStateListOf<String>()
 private val prefs by lazy { getSharedPreferences("native_sessions",MODE_PRIVATE) }
 override fun onCreate(savedInstanceState:Bundle?) { super.onCreate(savedInstanceState); window.addFlags(128); scan(); setContent { MaterialTheme(colorScheme=darkColorScheme(primary=Red,background=Ink,surface=Panel,onSurface=Bone,onBackground=Bone)) { Studio() } } }
 private fun scan(){ endpoints=midi?.devices?.flatMap { d -> d.ports.filter { it.type==MidiDeviceInfo.PortInfo.TYPE_INPUT }.map { p -> Endpoint(d,p.portNumber,"${d.properties.getString(MidiDeviceInfo.PROPERTY_NAME) ?: "MIDI"} / ${p.portNumber}") } } ?: emptyList() }
 private fun closeMidi(){ generation++; runCatching { port?.close() }; runCatching { device?.close() }; port=null; device=null; status="SIMULATION" }
 private fun connect(e:Endpoint){ closeMidi(); val g=generation; status="CONNEXION"; midi?.openDevice(e.info,{ d -> if(g!=generation){runCatching{d?.close()}}else{device=d; port=runCatching{d?.openInputPort(e.port)}.getOrNull(); status=if(port==null) "ÉCHEC MIDI" else "MIDI CONNECTÉ"} },handler) }
 private fun send(s:Int,a:Int,b:Int=0,len:Int=3){ val bytes=byteArrayOf((s+channel-1).toByte(),a.toByte(),b.toByte()); logs.add(0,bytes.take(len).joinToString(" "){ "%02X".format(it.toInt() and 255) }); if(logs.size>100)logs.removeAt(logs.lastIndex); try{port?.send(bytes,0,len)}catch(ex:Exception){closeMidi();status="MIDI PERDU"} }
 private fun cc(a:Int,b:Int)=send(176,a,b)
 override fun onDestroy(){closeMidi();super.onDestroy()}
 @Composable private fun Key(label:String,active:Boolean=false,action:()->Unit){ OutlinedButton(onClick=action,shape=RoundedCornerShape(5.dp),border=BorderStroke(1.dp,if(active)Red else Color(0xff776858)),colors=ButtonDefaults.outlinedButtonColors(containerColor=if(active)Color(0xff561b18)else Panel,contentColor=Bone),contentPadding=PaddingValues(horizontal=12.dp,vertical=8.dp)){Text(label,fontWeight=FontWeight.Bold,fontSize=13.sp)} }
 @Composable private fun Studio(){
  var tab by remember { mutableStateOf("LIVE") }; var model by remember { mutableStateOf("KP3") }; var x by remember { mutableIntStateOf(64) }; var y by remember { mutableIntStateOf(64) }; var program by remember { mutableIntStateOf(0) }; var depth by remember { mutableIntStateOf(100) }; var level by remember { mutableIntStateOf(100) }; var bpm by remember { mutableIntStateOf(174) }; var hold by remember { mutableStateOf(false) }; var loop by remember { mutableStateOf(true) }; var recording by remember { mutableStateOf(false) }; var playing by remember { mutableStateOf(false) }; var base by remember { mutableLongStateOf(0L) }; var lastTap by remember { mutableLongStateOf(0L) }; var job by remember { mutableStateOf<Job?>(null) }; var message by remember { mutableStateOf("") }; val motion=remember { mutableStateListOf<Motion>() }; val scope=rememberCoroutineScope(); val context=LocalContext.current
  val banner=remember { context.assets.open("banner.jpg").use { BitmapFactory.decodeStream(it).asImageBitmap() } }
  fun point(a:Int,b:Int,gate:Int=-1){x=a;y=b;cc(12,a);cc(13,b);if(gate>=0)cc(92,gate);if(recording&&motion.size<10000)motion.add(Motion(android.os.SystemClock.elapsedRealtime()-base,a,b,gate))}
  fun stop(){job?.cancel();job=null;playing=false;cc(92,0)}
  fun play(){stop();recording=false;if(motion.isEmpty())return;val copy=motion.toList();playing=true;job=scope.launch { do { var prev=0L; for(m in copy){delay((m.t-prev).coerceAtLeast(0));point(m.x,m.y,m.gate);prev=m.t};cc(92,0);delay(40) }while(loop);playing=false } }
  fun changeProgram(d:Int){program=(program+d).coerceIn(0,if(model=="KP3")127 else 149); if(program<=127)send(192,program,0,2)else message="Programmes 129–150 : sélection MIDI à valider"}
  fun save(){ val a=JSONArray();motion.forEach{a.put(JSONArray().put(it.t).put(it.x).put(it.y).put(it.gate))};prefs.edit().putString("session",JSONObject().put("model",model).put("program",program).put("depth",depth).put("level",level).put("bpm",bpm).put("channel",channel).put("motion",a).toString()).apply();message="Session native sauvegardée" }
  fun load(){stop();recording=false;runCatching{val j=JSONObject(prefs.getString("session",null)?:error("Aucune session native"));model=j.getString("model");program=j.getInt("program");depth=j.getInt("depth");level=j.getInt("level");bpm=j.getInt("bpm");channel=j.getInt("channel");motion.clear();val a=j.getJSONArray("motion");for(i in 0 until a.length()){val m=a.getJSONArray(i);motion.add(Motion(m.getLong(0),m.getInt(1),m.getInt(2),m.getInt(3)))};message="Session chargée localement (sans envoi MIDI)"}.onFailure{message=it.message?:"Erreur"} }
  Surface(modifier=Modifier.fillMaxSize(),color=Ink){Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(10.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
   Image(banner,contentDescription="mokteK Kaoss Studio",modifier=Modifier.fillMaxWidth().heightIn(max=150.dp),contentScale=ContentScale.FillWidth)
   Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){Text("NATIVE ENGINE / V3",color=Red,fontWeight=FontWeight.Bold);Text(status,color=if(status=="MIDI CONNECTÉ")Color.Green else Bone,fontSize=12.sp)}
   Row(Modifier.horizontalScroll(rememberScrollState()),horizontalArrangement=Arrangement.spacedBy(6.dp)){listOf("LIVE","MOTION","MIDI / USB","SESSIONS","STUDIO").forEach{Key(it,tab==it){tab=it}}}
   when(tab){
    "LIVE" -> {
     Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){Key("KP3",model=="KP3"){model="KP3";program=program.coerceAtMost(127)};Key("KP3+",model=="KP3+"){model="KP3+"};Key("HOLD",hold){hold=!hold;cc(95,if(hold)127 else 0);if(!hold)cc(92,0)}}
     Row(verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(8.dp)){Key("−"){changeProgram(-1)};Text("P.${(program+1).toString().padStart(3,'0')}",color=Red,fontSize=24.sp,fontWeight=FontWeight.Bold);Key("+"){changeProgram(1)};Text("X $x / Y $y",color=Bone)}
     Canvas(Modifier.fillMaxWidth().height(260.dp).border(2.dp,Red,RoundedCornerShape(9.dp)).pointerInput(Unit){awaitEachGesture { val down=awaitFirstDown(requireUnconsumed=false);stop();fun value(p:Offset,g:Int){point((p.x/size.width*127).toInt().coerceIn(0,127),(127-p.y/size.height*127).toInt().coerceIn(0,127),g)};value(down.position,127);down.consume();var last=0L;try{do{val e=awaitPointerEvent();val c=e.changes.firstOrNull{it.id==down.id}?:break;if(c.pressed&&c.uptimeMillis-last>=16){value(c.position,-1);last=c.uptimeMillis};c.consume()}while(c.pressed)}finally{if(!hold){cc(92,0);if(recording&&motion.size<10000)motion.add(Motion(android.os.SystemClock.elapsedRealtime()-base,x,y,0))}} } }){
      drawRect(Brush.radialGradient(listOf(Color(0xff56171a),Color(0xff19090c)),center=Offset(size.width*x/127f,size.height*(127-y)/127f),radius=size.width*.8f));for(i in 0..8){val px=size.width*i/8;val py=size.height*i/8;drawLine(Red.copy(alpha=.23f),Offset(px,0f),Offset(px,size.height));drawLine(Red.copy(alpha=.23f),Offset(0f,py),Offset(size.width,py))};val p=Offset(size.width*x/127f,size.height*(127-y)/127f);drawLine(Red,Offset(p.x,0f),Offset(p.x,size.height),2f);drawLine(Red,Offset(0f,p.y),Offset(size.width,p.y),2f);drawCircle(Red.copy(alpha=.25f),35f,p);drawCircle(Bone,9f,p)
     }
     Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(6.dp)){listOf("A","B","C","D").forEachIndexed { i,s -> Button(onClick={val ch=channel;send(144,36+i,127);scope.launch{delay(100);val old=channel;channel=ch;send(128,36+i,0);channel=old}},modifier=Modifier.weight(1f).height(64.dp),shape=RoundedCornerShape(6.dp),colors=ButtonDefaults.buttonColors(containerColor=Color(0xff651d1d),contentColor=Bone)){Text(s,fontSize=24.sp,fontWeight=FontWeight.Bold)} }}
     Text("FX DEPTH • $depth");Slider(value=depth.toFloat(),onValueChange={depth=it.toInt();cc(94,depth)},valueRange=0f..127f)
     Text("LEVEL • $level");Slider(value=level.toFloat(),onValueChange={level=it.toInt();cc(93,level)},valueRange=0f..127f)
     Row(verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(8.dp)){Key("−"){bpm=(bpm-1).coerceAtLeast(40)};Text("$bpm BPM",color=Red,fontSize=22.sp);Key("+"){bpm=(bpm+1).coerceAtMost(300)};Key("TAP"){val n=android.os.SystemClock.elapsedRealtime();if(lastTap>0&&n-lastTap in 200L..1500L)bpm=(60000/(n-lastTap)).toInt();lastTap=n}};Text("Tempo local — horloge MIDI non émise",fontSize=12.sp)
    }
    "MOTION" -> { Text("XY / AUTOMATION",color=Red,fontSize=22.sp);Text("${motion.size} événements • ${motion.lastOrNull()?.t ?: 0} ms");Row(horizontalArrangement=Arrangement.spacedBy(6.dp)){Key(if(recording)"FIN REC" else "REC",recording){if(recording)recording=false else{stop();motion.clear();base=android.os.SystemClock.elapsedRealtime();recording=true;tab="LIVE"}};Key("PLAY",playing){play()};Key("STOP"){stop();recording=false};Key("LOOP",loop){loop=!loop}};Text("REC ouvre le pad Live. Revenir ici pour terminer la capture.") }
    "MIDI / USB" -> {Text("CONNEXIONS",color=Red,fontSize=22.sp);Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){Key("ACTUALISER"){scan()};Key("DÉCONNECTER"){stop();closeMidi()}};Text("Canal MIDI : $channel");Slider(value=channel.toFloat(),onValueChange={channel=it.toInt().coerceIn(1,16)},valueRange=1f..16f,steps=14);if(endpoints.isEmpty())Text("Aucun port MIDI Android détecté. Vérifier OTG ou interface DIN.");endpoints.forEach{ e->Key(e.label){connect(e)}};val usb=context.getSystemService(USB_SERVICE) as? UsbManager;Text("USB : "+(usb?.deviceList?.values?.joinToString { "%04X:%04X".format(it.vendorId,it.productId) }?.ifEmpty{"aucun"}?:"indisponible"));Text("Journal émission (simulation comprise)");logs.take(25).forEach{Text(it,fontSize=12.sp)} }
    "SESSIONS" -> {Text("SESSION LOCALE",color=Red,fontSize=22.sp);Key("SAUVEGARDER"){save()};Key("CHARGER"){load()};Text("Une session native locale. Les anciennes sessions WebView restent séparées.")}
    else -> {Text("SAMPLE STUDIO",color=Red,fontSize=22.sp);Text("À développer : édition WAV, préécoute, formes d’onde et transfert matériel. Aucun transfert de samples dans cette version.")}
   };if(message.isNotEmpty())Text(message,color=Bone);Text("mokteK • FREE PARTY / SOUND SYSTEM • V3",fontSize=11.sp,color=Color(0xffab9582))
  }}
 }
}
