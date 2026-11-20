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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.text.font.FontFamily
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
private val Panel = Color(0xff211d1a)
private val Steel = Color(0xff887766)
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
 @Composable private fun Key(label:String,active:Boolean=false,action:()->Unit){
  Box(Modifier.heightIn(min=44.dp).clip(RoundedCornerShape(5.dp)).background(Brush.verticalGradient(listOf(if(active)Color(0xff72201e)else Color(0xff39322d),if(active)Color(0xff260b0b)else Ink))).border(1.dp,if(active)Red else Steel,RoundedCornerShape(5.dp)).clickable(onClick=action).padding(horizontal=13.dp,vertical=12.dp),contentAlignment=Alignment.Center){Text(label,color=if(active)Color(0xffffa397)else Bone,fontWeight=FontWeight.Bold,fontSize=12.sp)}
 }
 @Composable private fun Rack(title:String,modifier:Modifier=Modifier,content:@Composable ColumnScope.()->Unit){
  Column(modifier.clip(RoundedCornerShape(8.dp)).background(Brush.verticalGradient(listOf(Color(0xff332b25),Ink))).border(1.dp,Steel,RoundedCornerShape(8.dp)).padding(10.dp),verticalArrangement=Arrangement.spacedBy(7.dp)){
   Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){Text(title,color=Bone,fontSize=11.sp,fontWeight=FontWeight.Bold);Spacer(Modifier.weight(1f));Text("●",color=Steel,fontSize=10.sp)}
   content()
  }
 }
 @Composable private fun Dial(label:String,value:Int,onValue:(Int)->Unit){
  Column(Modifier.fillMaxWidth(),horizontalAlignment=Alignment.CenterHorizontally){
   Canvas(Modifier.size(69.dp)){
    val r=size.minDimension*.43f;val c=center
    drawCircle(Color(0xff0a0909),r*1.12f,c)
    drawArc(Steel,135f,270f,false,topLeft=Offset(c.x-r,c.y-r),size=androidx.compose.ui.geometry.Size(r*2,r*2),style=Stroke(3.dp.toPx()))
    drawArc(Red,135f,270f*value/127f,false,topLeft=Offset(c.x-r,c.y-r),size=androidx.compose.ui.geometry.Size(r*2,r*2),style=Stroke(3.dp.toPx()))
    drawCircle(Brush.radialGradient(listOf(Color(0xff71645a),Color(0xff1c1918)),center=c,radius=r),r*.77f,c)
    val angle=Math.toRadians((135+270*value/127.0));val end=Offset(c.x+(kotlin.math.cos(angle)*r*.64).toFloat(),c.y+(kotlin.math.sin(angle)*r*.64).toFloat());drawLine(Bone,c,end,3.dp.toPx())
   }
   Text("$label  $value",color=Bone,fontSize=12.sp,fontWeight=FontWeight.Bold)
   Slider(value=value.toFloat(),onValueChange={onValue(it.toInt())},valueRange=0f..127f,modifier=Modifier.height(40.dp))
  }
 }
 @Composable private fun Studio(){
  var tab by remember { mutableStateOf("LIVE") }; var model by remember { mutableStateOf("KP3") }; var x by remember { mutableIntStateOf(64) }; var y by remember { mutableIntStateOf(64) }; var program by remember { mutableIntStateOf(0) }; var depth by remember { mutableIntStateOf(100) }; var level by remember { mutableIntStateOf(100) }; var bpm by remember { mutableIntStateOf(174) }; var hold by remember { mutableStateOf(false) }; var loop by remember { mutableStateOf(true) }; var recording by remember { mutableStateOf(false) }; var playing by remember { mutableStateOf(false) }; var base by remember { mutableLongStateOf(0L) }; var lastTap by remember { mutableLongStateOf(0L) }; var job by remember { mutableStateOf<Job?>(null) }; var message by remember { mutableStateOf("") }; val motion=remember { mutableStateListOf<Motion>() }; val scope=rememberCoroutineScope(); val context=LocalContext.current; val wide=LocalConfiguration.current.screenWidthDp>=850; var stage by remember { mutableStateOf(false) }; val flashes=remember { mutableStateListOf(false,false,false,false) }
  val banner=remember { context.assets.open("banner.jpg").use { BitmapFactory.decodeStream(it).asImageBitmap() } }
  fun point(a:Int,b:Int,gate:Int=-1){x=a;y=b;cc(12,a);cc(13,b);if(gate>=0)cc(92,gate);if(recording&&motion.size<10000)motion.add(Motion(android.os.SystemClock.elapsedRealtime()-base,a,b,gate))}
  fun stop(){job?.cancel();job=null;playing=false;cc(92,0)}
  fun play(){stop();recording=false;if(motion.isEmpty())return;val copy=motion.toList();playing=true;job=scope.launch { do { var prev=0L; for(m in copy){delay((m.t-prev).coerceAtLeast(0));point(m.x,m.y,m.gate);prev=m.t};cc(92,0);delay(40) }while(loop);playing=false } }
  fun changeProgram(d:Int){program=(program+d).coerceIn(0,if(model=="KP3")127 else 149); if(program<=127)send(192,program,0,2)else message="Programmes 129–150 : sélection MIDI à valider"}
  fun save(){ val a=JSONArray();motion.forEach{a.put(JSONArray().put(it.t).put(it.x).put(it.y).put(it.gate))};prefs.edit().putString("session",JSONObject().put("model",model).put("program",program).put("depth",depth).put("level",level).put("bpm",bpm).put("channel",channel).put("motion",a).toString()).apply();message="Session native sauvegardée" }
  fun load(){stop();recording=false;runCatching{val j=JSONObject(prefs.getString("session",null)?:error("Aucune session native"));model=j.getString("model");program=j.getInt("program");depth=j.getInt("depth");level=j.getInt("level");bpm=j.getInt("bpm");channel=j.getInt("channel");motion.clear();val a=j.getJSONArray("motion");for(i in 0 until a.length()){val m=a.getJSONArray(i);motion.add(Motion(m.getLong(0),m.getInt(1),m.getInt(2),m.getInt(3)))};message="Session chargée localement (sans envoi MIDI)"}.onFailure{message=it.message?:"Erreur"} }
  Surface(modifier=Modifier.fillMaxSize(),color=Ink){Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(10.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
   if(!stage) Image(banner,contentDescription="mokteK Kaoss Studio",modifier=Modifier.fillMaxWidth().heightIn(max=if(wide) 85.dp else 150.dp),contentScale=ContentScale.FillWidth)
   Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){Column { Text("mokteK / KAOSS STUDIO",color=Bone,fontWeight=FontWeight.Bold,fontSize=14.sp);Text(status,color=if(status=="MIDI CONNECTÉ")Color.Green else Bone,fontSize=11.sp) };Key(if(stage)"SORTIR SCÈNE" else "SCÈNE",stage){stage=!stage;tab="LIVE"}}
   if(!stage) Row(Modifier.horizontalScroll(rememberScrollState()),horizontalArrangement=Arrangement.spacedBy(6.dp)){listOf("LIVE","MOTION","MIDI / USB","SESSIONS","STUDIO").forEach{Key(it,tab==it){tab=it}}}
   when(tab){
    "LIVE" -> {
     val controls: @Composable ()->Unit = {
     Row(Modifier.horizontalScroll(rememberScrollState()),horizontalArrangement=Arrangement.spacedBy(8.dp)){Key("KP3",model=="KP3"){model="KP3";program=program.coerceAtMost(127)};Key("KP3+",model=="KP3+"){model="KP3+"}}
     Row {Key("HOLD",hold){hold=!hold;cc(95,if(hold)127 else 0);if(!hold)cc(92,0)}}
     Row(Modifier.horizontalScroll(rememberScrollState()),verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(6.dp)){Key("−"){changeProgram(-1)};Text("P.${(program+1).toString().padStart(3,'0')}",color=Red,fontSize=24.sp,fontWeight=FontWeight.Bold);Key("+"){changeProgram(1)}};Text("X $x / Y $y",color=Bone,fontFamily=FontFamily.Monospace)
     Row(Modifier.horizontalScroll(rememberScrollState()),verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(6.dp)){Key("−"){bpm=(bpm-1).coerceAtLeast(40)};Text("$bpm BPM",color=Red,fontSize=22.sp);Key("+"){bpm=(bpm+1).coerceAtMost(300)}};Row {Key("TAP"){val n=android.os.SystemClock.elapsedRealtime();if(lastTap>0&&n-lastTap in 200L..1500L)bpm=(60000/(n-lastTap)).toInt();lastTap=n}};Text("Tempo local — horloge MIDI non émise",fontSize=12.sp)
     }
     val touch: @Composable ()->Unit = {
     Canvas(Modifier.fillMaxWidth().height(if(wide) 235.dp else 300.dp).border(2.dp,Red,RoundedCornerShape(9.dp)).pointerInput(hold,recording,channel){awaitEachGesture { val down=awaitFirstDown(requireUnconsumed=false);stop();fun value(p:Offset,g:Int){point((p.x/size.width*127).toInt().coerceIn(0,127),(127-p.y/size.height*127).toInt().coerceIn(0,127),g)};value(down.position,127);down.consume();var last=0L;try{do{val e=awaitPointerEvent();val c=e.changes.firstOrNull{it.id==down.id}?:break;if(c.pressed&&c.uptimeMillis-last>=16){value(c.position,-1);last=c.uptimeMillis};c.consume()}while(c.pressed)}finally{if(!hold){cc(92,0);if(recording&&motion.size<10000)motion.add(Motion(android.os.SystemClock.elapsedRealtime()-base,x,y,0))}} } }){
      drawRect(Brush.radialGradient(listOf(Color(0xff56171a),Color(0xff19090c)),center=Offset(size.width*x/127f,size.height*(127-y)/127f),radius=size.width*.8f));for(i in 0..8){val px=size.width*i/8;val py=size.height*i/8;drawLine(Red.copy(alpha=.23f),Offset(px,0f),Offset(px,size.height));drawLine(Red.copy(alpha=.23f),Offset(0f,py),Offset(size.width,py))};val p=Offset(size.width*x/127f,size.height*(127-y)/127f);drawLine(Red,Offset(p.x,0f),Offset(p.x,size.height),2f);drawLine(Red,Offset(0f,p.y),Offset(size.width,p.y),2f);drawCircle(Red.copy(alpha=.25f),35f,p);drawCircle(Red.copy(alpha=.12f),55f,p);drawCircle(Red,19f,p,style=Stroke(2.dp.toPx()));drawCircle(Bone,7f,p);drawRect(Steel.copy(alpha=.45f),style=Stroke(3.dp.toPx()))
     }
     Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(6.dp)){listOf("A","B","C","D").forEachIndexed { i,s -> Button(onClick={flashes[i]=true;val ch=channel;send(144,36+i,127);scope.launch{delay(100);flashes[i]=false;val old=channel;channel=ch;send(128,36+i,0);channel=old}},modifier=Modifier.weight(1f).height(64.dp),shape=RoundedCornerShape(6.dp),colors=ButtonDefaults.buttonColors(containerColor=if(flashes[i])Red else Color(0xff651d1d),contentColor=Bone)){Text(s,fontSize=24.sp,fontWeight=FontWeight.Bold)} }}

     }
     val effects: @Composable ()->Unit = {
     Dial("FX DEPTH",depth){depth=it;cc(94,depth)}
     Dial("LEVEL",level){level=it;cc(93,level)}
     Text("MOTION / XY",color=Bone,fontSize=12.sp,fontWeight=FontWeight.Bold)
     Key(if(recording)"FIN REC" else "REC",recording){if(recording)recording=false else{stop();motion.clear();base=android.os.SystemClock.elapsedRealtime();recording=true}}
     Row(Modifier.horizontalScroll(rememberScrollState()),horizontalArrangement=Arrangement.spacedBy(4.dp)){Key("PLAY",playing){play()};Key("STOP"){stop();recording=false}}
     Key("LOOP",loop){loop=!loop}
     Text("${motion.size} événements",fontSize=11.sp)
     }
     if(wide){Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(8.dp)){
      Rack("APPAREIL / TEMPO",Modifier.weight(1.05f)){controls()}
      Rack("XY PERFORMANCE",Modifier.weight(1.65f)){touch()}
      Rack("FX / MOTION",Modifier.weight(1f)){effects()}
     }}else{
      Rack("APPAREIL / TEMPO"){controls()}
      Rack("XY PERFORMANCE"){touch()}
      Rack("FX / MOTION"){effects()}
     }

    }
    "MOTION" -> { Text("XY / AUTOMATION",color=Red,fontSize=22.sp);Text("${motion.size} événements • ${motion.lastOrNull()?.t ?: 0} ms");Row(horizontalArrangement=Arrangement.spacedBy(6.dp)){Key(if(recording)"FIN REC" else "REC",recording){if(recording)recording=false else{stop();motion.clear();base=android.os.SystemClock.elapsedRealtime();recording=true;tab="LIVE"}};Key("PLAY",playing){play()};Key("STOP"){stop();recording=false};Key("LOOP",loop){loop=!loop}};Text("REC ouvre le pad Live. Revenir ici pour terminer la capture.") }
    "MIDI / USB" -> {Text("CONNEXIONS",color=Red,fontSize=22.sp);Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){Key("ACTUALISER"){scan()};Key("DÉCONNECTER"){stop();closeMidi()}};Text("Canal MIDI : $channel");Slider(value=channel.toFloat(),onValueChange={channel=it.toInt().coerceIn(1,16)},valueRange=1f..16f,steps=14);if(endpoints.isEmpty())Text("Aucun port MIDI Android détecté. Vérifier OTG ou interface DIN.");endpoints.forEach{ e->Key(e.label){connect(e)}};val usb=context.getSystemService(USB_SERVICE) as? UsbManager;Text("USB : "+(usb?.deviceList?.values?.joinToString { "%04X:%04X".format(it.vendorId,it.productId) }?.ifEmpty{"aucun"}?:"indisponible"));Text("Journal émission (simulation comprise)");logs.take(25).forEach{Text(it,fontSize=12.sp)} }
    "SESSIONS" -> {Text("SESSION LOCALE",color=Red,fontSize=22.sp);Key("SAUVEGARDER"){save()};Key("CHARGER"){load()};Text("Une session native locale. Les anciennes sessions WebView restent séparées.")}
    else -> { SampleStudio() }
   };if(message.isNotEmpty())Text(message,color=Bone);Text("mokteK • FREE PARTY / SOUND SYSTEM • V6",fontSize=11.sp,color=Color(0xffab9582))
  }}
 }
}
