package org.moktek.kaoss
import android.media.AudioTrack
import android.media.AudioAttributes
import android.media.AudioFormat
import android.content.Context
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.*
private val flame=Color(0xffff493e)
private val ivory=Color(0xffe9dac2)
internal class PatternState { val grid=mutableStateListOf<Boolean>().apply{repeat(384){add(false)}};val volumes=mutableStateListOf(1f,.65f,.65f,.7f,.55f,.65f);var bpm by mutableIntStateOf(174);var steps by mutableIntStateOf(16);var page by mutableIntStateOf(0);init{demo()};fun demo(){for(i in grid.indices)grid[i]=false; val hits=listOf(listOf(0,4,8,12),listOf(3,7,10,14),listOf(0,6,8,14),listOf(4,12),listOf(2,6,10,14),listOf(11,15));for(l in 0..5)for(s in 0 until 64)grid[l*64+s]=s%16 in hits[l]} }
@Composable internal fun TribeSequencer(state:PatternState){
 val context=LocalContext.current;val scope=rememberCoroutineScope();val prefs=remember{context.getSharedPreferences("patterns_v9",Context.MODE_PRIVATE)}
 var track by remember{mutableStateOf<AudioTrack?>(null)};var busy by remember{mutableStateOf(false)};var cursor by remember{mutableIntStateOf(-1)};var msg by remember{mutableStateOf("Touchez une case pour activer un son.")};var pending by remember{mutableStateOf<ByteArray?>(null)}
 fun stop(){val t=track;track=null;cursor=-1;runCatching{t?.release()}}
 DisposableEffect(Unit){onDispose{stop()}}
 LaunchedEffect(track){val t=track?:return@LaunchedEffect;while(isActive){val frames=t.playbackHeadPosition.toLong() and 0xffffffffL;cursor=((frames/(44100*60.0/state.bpm/4)).toLong()%state.steps).toInt();delay(30)}}
 val export=rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("audio/wav")){uri->val data=pending;pending=null;if(uri!=null&&data!=null)scope.launch{try{withContext(Dispatchers.IO){context.contentResolver.openOutputStream(uri,"wt")?.use{it.write(data)}?:error("Écriture impossible")};msg="Boucle exportée"}catch(e:Exception){msg=e.message?:"Erreur export"}}}
 fun render(play:Boolean){stop();busy=true;val bpm=state.bpm;val steps=state.steps;val grid=state.grid.toList();val vols=state.volumes.toList();scope.launch{try{val pcm=withContext(Dispatchers.Default){PatternEngine.render(bpm,steps,grid,vols)};if(play){val t=AudioTrack.Builder().setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).build()).setAudioFormat(AudioFormat.Builder().setEncoding(AudioFormat.ENCODING_PCM_16BIT).setSampleRate(44100).setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build()).setTransferMode(AudioTrack.MODE_STATIC).setBufferSizeInBytes(pcm.size).build();track=t;check(t.state==AudioTrack.STATE_INITIALIZED);check(t.write(pcm,0,pcm.size)==pcm.size);check(t.setLoopPoints(0,pcm.size/2,-1)==0);t.play();msg="Lecture locale • STOP pour modifier"}else{pending=PatternEngine.wav(pcm);export.launch("moktek_pattern.wav")}}catch(e:CancellationException){throw e}catch(e:Exception){stop();msg=e.message?:"Erreur audio"}finally{busy=false}}}
 val edit=!busy&&track==null
 Column(Modifier.fillMaxWidth().border(1.dp,Color(0xff887766),RoundedCornerShape(8.dp)).background(Brush.verticalGradient(listOf(Color(0xff352921),Color(0xff110e0e))),RoundedCornerShape(8.dp)).padding(10.dp),verticalArrangement=Arrangement.spacedBy(9.dp)){
 Text("TRIBE / SEQUENCER",fontSize=21.sp,fontWeight=FontWeight.Black,color=ivory);Text("6 pistes • boucle locale",fontSize=12.sp,color=ivory)
 Row(verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(8.dp)){Button(onClick={render(true)},enabled=edit){Text("PLAY")};OutlinedButton(onClick={stop()},enabled=track!=null){Text("STOP")};Text("${state.bpm} BPM",color=flame,fontSize=23.sp,fontWeight=FontWeight.Bold)}
 Slider(state.bpm.toFloat(),{state.bpm=it.toInt()},valueRange=70f..240f,enabled=edit)
 Row(horizontalArrangement=Arrangement.spacedBy(5.dp)){for(n in listOf(16,32,64)){FilterChip(selected=state.steps==n,onClick={state.steps=n;state.page=0},label={Text("$n pas")},enabled=edit)}}
 Row(horizontalArrangement=Arrangement.spacedBy(5.dp)){for(p in 0 until state.steps/16){FilterChip(selected=state.page==p,onClick={state.page=p},label={Text("${p*16+1}–${p*16+16}")})}}
 for(lane in 0..5){Column(Modifier.fillMaxWidth().background(Color(0xff191413),RoundedCornerShape(6.dp)).padding(6.dp)){Row(verticalAlignment=Alignment.CenterVertically){Text(PatternEngine.names[lane],color=ivory,fontWeight=FontWeight.Bold,modifier=Modifier.weight(1f));Text("VOL ${(state.volumes[lane]*100).toInt()}%",fontSize=11.sp);Slider(state.volumes[lane],{state.volumes[lane]=it},modifier=Modifier.width(110.dp).height(36.dp),enabled=edit)};for(half in 0..1){Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(4.dp)){for(i in 0..7){val step=state.page*16+half*8+i;val index=lane*64+step;val on=state.grid[index];val lit=cursor==step;Box(Modifier.weight(1f).height(44.dp).background(Brush.verticalGradient(listOf(if(on)Color(0xffe84329)else Color(0xff46372e),if(on)Color(0xff8d1814)else Color(0xff211b18))),RoundedCornerShape(4.dp)).border(if(lit)3.dp else 1.dp,if(lit)Color.White else if(on)flame else Color(0xff75614e),RoundedCornerShape(4.dp)).clickable(enabled=edit){state.grid[index]=!on}.semantics{contentDescription="${PatternEngine.names[lane]} pas ${step+1}";stateDescription=if(on)"Activé" else "Désactivé"},contentAlignment=Alignment.Center){Text("${step+1}",color=ivory,fontSize=11.sp,fontWeight=FontWeight.Bold)}}}}}}
 Row(horizontalArrangement=Arrangement.spacedBy(6.dp)){OutlinedButton(onClick={state.demo()},enabled=edit){Text("DÉMO")};OutlinedButton(onClick={for(i in state.grid.indices)state.grid[i]=false},enabled=edit){Text("VIDER")}}
 Row(horizontalArrangement=Arrangement.spacedBy(6.dp)){OutlinedButton(onClick={prefs.edit().putString("grid",state.grid.joinToString(""){if(it)"1" else "0"}).putInt("bpm",state.bpm).putInt("steps",state.steps).putString("vol",state.volumes.joinToString(",")).apply();msg="Pattern sauvegardé"},enabled=edit){Text("SAUVER")};OutlinedButton(onClick={runCatching{val s=prefs.getString("grid",null)?:error("Aucun pattern");require(s.length==384);val v=prefs.getString("vol","")!!.split(",").map{it.toFloat().coerceIn(0f,1f)};require(v.size==6);for(i in s.indices)state.grid[i]=s[i]=='1';for(i in 0..5)state.volumes[i]=v[i];state.bpm=prefs.getInt("bpm",174).coerceIn(70,240);state.steps=prefs.getInt("steps",16).takeIf{it in listOf(16,32,64)}?:16;state.page=0;msg="Pattern chargé"}.onFailure{msg=it.message?:"Erreur"}},enabled=edit){Text("CHARGER")}}
 Button(onClick={render(false)},enabled=edit,modifier=Modifier.fillMaxWidth()){Text("EXPORTER BOUCLE WAV")};if(busy)LinearProgressIndicator(Modifier.fillMaxWidth());Text(msg,fontSize=12.sp);Text("Préécoute mono • pas de transfert KP3",fontSize=11.sp,color=ivory)
 }
}
