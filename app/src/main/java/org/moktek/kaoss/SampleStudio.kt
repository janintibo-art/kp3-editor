package org.moktek.kaoss

import android.content.Context
import android.net.Uri
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.abs

private data class Wave(val rate:Int,val channels:Int,val pcm:ByteArray) {
 val frames get()=pcm.size/(channels*2)
 fun slice(a:Int,b:Int)=pcm.copyOfRange(a*channels*2,b*channels*2)
 fun peaks():FloatArray { val out=FloatArray(512); val buf=ByteBuffer.wrap(pcm).order(ByteOrder.LITTLE_ENDIAN); for(i in 0 until frames){val bin=(i.toLong()*512/frames).toInt();repeat(channels){out[bin]=maxOf(out[bin],abs(buf.short.toInt())/32768f)}};return out }
 fun export(a:Int,b:Int):ByteArray {val data=slice(a,b);return ByteBuffer.allocate(44+data.size).order(ByteOrder.LITTLE_ENDIAN).apply{put("RIFF".toByteArray());putInt(36+data.size);put("WAVEfmt ".toByteArray());putInt(16);putShort(1.toShort());putShort(channels.toShort());putInt(rate);putInt(rate*channels*2);putShort((channels*2).toShort());putShort(16.toShort());put("data".toByteArray());putInt(data.size);put(data)}.array()}
}
private fun loadWave(context:Context,uri:Uri):Wave {
 val bytes=context.contentResolver.openInputStream(uri)?.use{input->val out=ByteArrayOutputStream();val chunk=ByteArray(16384);while(true){val n=input.read(chunk);if(n<0)break;require(out.size()+n<=32*1024*1024){"Fichier trop volumineux (32 Mio maximum)"};out.write(chunk,0,n)};out.toByteArray()}?:error("Lecture impossible")
 val b=ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
 fun tag(i:Int)=String(bytes,i,4,Charsets.US_ASCII)
 require(bytes.size>=44&&tag(0)=="RIFF"&&tag(8)=="WAVE"){"Format WAV RIFF attendu"}
 var pos=12;var rate=0;var channels=0;var fmt=false;var data:ByteArray?=null
 while(pos<=bytes.size-8){val length=b.getInt(pos+4);val start=pos+8;require(length>=0&&length<=bytes.size-start){"Bloc WAV invalide"};when(tag(pos)){"fmt "->{require(length>=16);channels=b.getShort(start+2).toInt();rate=b.getInt(start+4);fmt=b.getShort(start).toInt()==1&&b.getShort(start+14).toInt()==16};"data"->data=bytes.copyOfRange(start,start+length)};pos=start+length+(length and 1)}
 require(fmt&&channels in 1..2&&rate in 8000..48000){"WAV PCM 16 bits, mono/stéréo, 8–48 kHz uniquement"};val pcm=data?:error("Données audio absentes");require(pcm.size>=channels*2&&pcm.size%(channels*2)==0){"Données audio invalides"};return Wave(rate,channels,pcm)
}
@Composable internal fun SampleStudio(){
 val context=LocalContext.current;val scope=rememberCoroutineScope();var wave by remember{mutableStateOf<Wave?>(null)};var peaks by remember{mutableStateOf(FloatArray(0))};var start by remember{mutableStateOf(0f)};var end by remember{mutableStateOf(1f)};var loop by remember{mutableStateOf(false)};var busy by remember{mutableStateOf(false)};var message by remember{mutableStateOf("Importer un WAV PCM 16 bits")};var track by remember{mutableStateOf<AudioTrack?>(null)};var pending by remember{mutableStateOf<ByteArray?>(null)}
 fun stop(){val old=track;track=null;runCatching{old?.stop()};runCatching{old?.release()}}
 DisposableEffect(Unit){onDispose{stop()}}
 var original by remember{mutableStateOf<Wave?>(null)};var undo by remember{mutableStateOf<Wave?>(null)};var gain by remember{mutableStateOf(1f)};var bpm by remember{mutableStateOf(174f)};var pitch by remember{mutableStateOf(55f)};var decay by remember{mutableStateOf(.12f)};var drive by remember{mutableStateOf(2f)}
 fun edit(action:String, work:()->Wave){stop();busy=true;val before=wave;scope.launch{try{val result=withContext(Dispatchers.Default){val next=work();next to next.peaks()};undo=before;wave=result.first;peaks=result.second;message=action}catch(e:Exception){message=e.message?:"Traitement impossible"}finally{busy=false}}}
 val picker=rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()){uri->if(uri!=null){stop();busy=true;scope.launch{try{val result=withContext(Dispatchers.IO){val w=loadWave(context,uri);w to w.peaks()};wave=result.first;original=result.first;undo=null;peaks=result.second;start=0f;end=1f;message="Audio chargé"}catch(e:Exception){message=e.message?:"Import impossible"}finally{busy=false}}}}
 val exporter=rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("audio/wav")){uri->val data=pending;pending=null;if(uri!=null&&data!=null){scope.launch{try{withContext(Dispatchers.IO){context.contentResolver.openOutputStream(uri,"wt")?.use{it.write(data)}?:error("Écriture impossible")};message="WAV exporté"}catch(e:Exception){message=e.message?:"Export impossible"}}}}
 val red=Color(0xffff493e)
 Text("SAMPLE STUDIO",color=red,fontSize=24.sp)
 Text("IMPORT / CUT / LOOP / EXPORT",color=Color(0xffe9dac2),fontSize=12.sp)
 Button(onClick={picker.launch(arrayOf("audio/*","application/octet-stream"))},enabled=!busy){Text("IMPORTER WAV")}
 Text("SOUND LAB • KICK FACTORY",color=red,fontSize=20.sp)
 Text("Tempo : ${bpm.toInt()} BPM");Slider(bpm,{bpm=it},valueRange=70f..240f,enabled=!busy)
 Text("Kick : ${pitch.toInt()} Hz • decay ${ (decay*1000).toInt()} ms • drive ${"%.1f".format(drive)}")
 Slider(pitch,{pitch=it},valueRange=35f..100f,enabled=!busy)
 Slider(decay,{decay=it},valueRange=.03f.. .4f,enabled=!busy)
 Slider(drive,{drive=it},valueRange=1f..8f,enabled=!busy)
 Button(onClick={val tempo=bpm.toInt();val p=pitch;val d=decay;val g=drive;start=0f;end=1f;edit("Kick généré"){Wave(44100,1,SoundLab.kick(44100,tempo,p,d,g))}},enabled=!busy){Text("GÉNÉRER KICK")}
 if(busy) LinearProgressIndicator(Modifier.fillMaxWidth())
 wave?.let{w->
 val a=(start*w.frames).toInt().coerceIn(0,w.frames-1);val z=(end*w.frames).toInt().coerceIn(a+1,w.frames)
 Text("${w.rate} Hz • ${w.channels} canal(aux) • PCM 16 bits")
 Canvas(Modifier.fillMaxWidth().height(160.dp).background(Color(0xff19090c))){drawRect(red.copy(alpha=.16f),topLeft=Offset(size.width*start,0f),size=androidx.compose.ui.geometry.Size(size.width*(end-start),size.height));peaks.forEachIndexed{i,p->val x=i*size.width/peaks.size;drawLine(if(i/512f in start..end)red else Color.Gray,Offset(x,size.height*(.5f-p*.46f)),Offset(x,size.height*(.5f+p*.46f)),strokeWidth=2f)};drawLine(Color.White,Offset(size.width*start,0f),Offset(size.width*start,size.height));drawLine(Color.White,Offset(size.width*end,0f),Offset(size.width*end,size.height))}
 Text("TRANSFORMATIONS • sélection uniquement",color=red)
 for(pair in listOf(listOf("NORMALISER","INVERSER"),listOf("FONDU IN","FONDU OUT"))){Row(horizontalArrangement=Arrangement.spacedBy(6.dp)){for(mode in pair){OutlinedButton(onClick={edit(mode){w.copy(pcm=SoundLab.transform(w.pcm,w.channels,a,z,mode))}},enabled=!busy,modifier=Modifier.weight(1f)){Text(mode,fontSize=11.sp)}}}}
 Text("Gain : ${"%.2f".format(gain)} ×");Slider(gain,{gain=it},valueRange=0f..2f,enabled=!busy)
 Button(onClick={val g=gain;edit("Gain appliqué"){w.copy(pcm=SoundLab.transform(w.pcm,w.channels,a,z,"GAIN",g))}},enabled=!busy){Text("APPLIQUER GAIN")}
 Row(horizontalArrangement=Arrangement.spacedBy(6.dp)){OutlinedButton(onClick={val old=undo;if(old!=null){start=0f;end=1f;edit("Modification annulée"){old}}},enabled=!busy&&undo!=null){Text("ANNULER / RÉTABLIR")};OutlinedButton(onClick={val old=original;if(old!=null){start=0f;end=1f;edit("Original restauré"){old}}},enabled=!busy&&original!=null){Text("ORIGINAL")}}
 Button(onClick={busy=true;scope.launch{try{val found=withContext(Dispatchers.Default){SoundLab.bpm(w.pcm,w.rate,w.channels)};if(found!=null){bpm=found.toFloat();message="Tempo estimé : $found BPM (à confirmer)"}else message="Tempo non identifiable"}finally{busy=false}}},enabled=!busy){Text("ESTIMER BPM")}
 Row(horizontalArrangement=Arrangement.spacedBy(4.dp)){for(beats in listOf(1,4,8)){OutlinedButton(onClick={stop();end=(start+beats*60f/bpm*w.rate/w.frames).coerceIn(start+.001f,1f)},enabled=!busy){Text("$beats temps")}}}
 Text("Début : %.3f s".format(a.toDouble()/w.rate));Slider(start,{stop();start=it.coerceAtMost(end-0.001f).coerceAtLeast(0f)},valueRange=0f..1f,enabled=!busy)
 Text("Fin : %.3f s • durée %.3f s".format(z.toDouble()/w.rate,(z-a).toDouble()/w.rate));Slider(end,{stop();end=it.coerceAtLeast(start+0.001f).coerceAtMost(1f)},valueRange=0f..1f,enabled=!busy)
 Row(verticalAlignment=androidx.compose.ui.Alignment.CenterVertically){Checkbox(loop,{stop();loop=it},enabled=!busy);Text("Écoute en boucle")}
 Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){Button(onClick={stop();try{val data=w.slice(a,z);val t=AudioTrack.Builder().setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build()).setAudioFormat(AudioFormat.Builder().setEncoding(AudioFormat.ENCODING_PCM_16BIT).setSampleRate(w.rate).setChannelMask(if(w.channels==1)AudioFormat.CHANNEL_OUT_MONO else AudioFormat.CHANNEL_OUT_STEREO).build()).setTransferMode(AudioTrack.MODE_STATIC).setBufferSizeInBytes(data.size).build();track=t;check(t.state==AudioTrack.STATE_INITIALIZED){"AudioTrack indisponible"};check(t.write(data,0,data.size)==data.size){"Préécoute incomplète"};if(loop)check(t.setLoopPoints(0,z-a,-1)==0){"Boucle indisponible"};t.play();message="Préécoute locale"}catch(e:Exception){stop();message=e.message?:"Lecture impossible"}},enabled=!busy){Text("PLAY")};OutlinedButton(onClick={stop();message="Arrêt"}){Text("STOP")}}
 Button(onClick={stop();pending=w.export(a,z);exporter.launch("moktek_sample.wav")},enabled=!busy){Text("EXPORTER LA SÉLECTION")}
 }
 Text(message);Text("WAV local uniquement • aucun transfert KP3 dans cette version",fontSize=12.sp)
}
