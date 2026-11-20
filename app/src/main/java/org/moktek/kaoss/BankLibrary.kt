package org.moktek.kaoss

import android.content.Context
import android.net.Uri
import android.media.MediaPlayer
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.UUID

internal data class Bank(val file:String="",val name:String="",val bpm:Int=174,val loop:Boolean=true,val mask:Int=255)
internal class BankStore(private val context:Context){
 private val dir=File(context.filesDir,"banks_v11").apply{mkdirs()}
 private val prefs=context.getSharedPreferences("banks_v11",Context.MODE_PRIVATE)
 fun read():List<Bank> = runCatching{val a=JSONArray(prefs.getString("banks","[]")); List(4){i->val j=a.optJSONObject(i);if(j==null)Bank() else Bank(j.optString("file"),j.optString("name"),j.optInt("bpm",174).coerceIn(40,300),j.optBoolean("loop",true),j.optInt("mask",255) and 255)}}.getOrElse{List(4){Bank()}}
 fun save(banks:List<Bank>){val a=JSONArray();banks.forEach{a.put(JSONObject().put("file",it.file).put("name",it.name).put("bpm",it.bpm).put("loop",it.loop).put("mask",it.mask))};check(prefs.edit().putString("banks",a.toString()).commit()){ "Sauvegarde impossible" };val keep=banks.map{it.file}.toSet();dir.listFiles()?.filter{it.name.endsWith(".wav")&&it.name !in keep}?.forEach{it.delete()}}
 fun add(w:Wave,name:String,bpm:Int):Bank{val id=UUID.randomUUID().toString()+".wav";File(dir,id).writeBytes(w.export(0,w.frames));return Bank(id,name,bpm)}
 fun wave(b:Bank):Wave = loadWave(context,Uri.fromFile(File(dir,b.file)))
}
internal fun mutedSlices(w:Wave,mask:Int):Wave {val data=w.pcm.copyOf();val stride=w.channels*2;for(i in 0..7){if(mask and (1 shl i)==0){val a=(w.frames.toLong()*i/8).toInt()*stride;val z=(w.frames.toLong()*(i+1)/8).toInt()*stride;data.fill(0.toByte(),a,z)}};return w.copy(pcm=data)}

@Composable internal fun BankLibrary(){
 val context=LocalContext.current;val store=remember{BankStore(context)};val scope=rememberCoroutineScope()
 var banks by remember{mutableStateOf(store.read())};var selected by remember{mutableIntStateOf(0)};var target by remember{mutableIntStateOf(1)};var busy by remember{mutableStateOf(false)};var msg by remember{mutableStateOf("Bibliothèque locale • aucun transfert matériel")};var confirm by remember{mutableStateOf("")};var peaks by remember{mutableStateOf(FloatArray(0))};var duration by remember{mutableStateOf(0.0)};var player by remember{mutableStateOf<MediaPlayer?>(null)};var pending by remember{mutableStateOf<ByteArray?>(null)}
 val b=banks[selected];val red=Color(0xffff493e);val bone=Color(0xffe9dac2)
 fun stop(){val p=player;player=null;runCatching{p?.release()}}
 DisposableEffect(Unit){onDispose{stop()}}
 fun save(next:List<Bank>,text:String){stop();try{store.save(next);banks=next;msg=text}catch(e:Exception){msg=e.message?:"Erreur de sauvegarde"}}
 fun update(next:Bank){save(banks.toMutableList().apply{set(selected,next)},"Banque ${'A'+selected} sauvegardée")}
 LaunchedEffect(b.file){peaks=FloatArray(0);duration=0.0;if(b.file.isNotEmpty()){runCatching{withContext(Dispatchers.IO){val w=store.wave(b);w.peaks() to w.frames.toDouble()/w.rate}}.onSuccess{peaks=it.first;duration=it.second}.onFailure{msg="Audio indisponible"}}}
 val picker=rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()){uri->if(uri!=null){val slot=selected;val before=banks;stop();busy=true;scope.launch{try{val next=withContext(Dispatchers.IO){val name=context.contentResolver.query(uri,arrayOf(OpenableColumns.DISPLAY_NAME),null,null,null)?.use{if(it.moveToFirst())it.getString(0) else null}?:"Sample WAV";val w=loadWave(context,uri);store.add(w,name.take(100),before[slot].bpm)};save(before.toMutableList().apply{set(slot,next)},"WAV importé dans ${'A'+slot}")}catch(e:Exception){msg=e.message?:"Import impossible"}finally{busy=false}}}}
 val exporter=rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("audio/wav")){uri->val data=pending;pending=null;if(uri!=null&&data!=null){scope.launch{try{withContext(Dispatchers.IO){context.contentResolver.openOutputStream(uri,"wt")?.use{it.write(data)}?:error("Écriture impossible")};msg="WAV exporté"}catch(e:Exception){msg=e.message?:"Export impossible"}}}}
 @Composable fun Pad(label:String,active:Boolean,modifier:Modifier=Modifier,action:()->Unit){val shape=RoundedCornerShape(6.dp);Box(modifier.height(48.dp).background(Brush.verticalGradient(if(active)listOf(Color(0xff83241f),Color(0xff34100e))else listOf(Color(0xff403830),Color(0xff171514))),shape).border(1.dp,if(active)red else Color(0xff897762),shape).clickable(enabled=!busy,onClick=action),contentAlignment=Alignment.Center){Text(label,color=bone,fontSize=12.sp,fontWeight=FontWeight.Bold)}}
 Text("SAMPLE LIBRARIAN",color=red,fontSize=22.sp,fontWeight=FontWeight.Bold);Text("4 banques • préparation KP3 / KP3+",color=bone,fontSize=12.sp)
 Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(5.dp)){banks.forEachIndexed{i,item->Pad("${'A'+i} ${if(item.file.isEmpty())"–" else "●"}",selected==i,Modifier.weight(1f)){stop();selected=i;if(target==i)target=(i+1)%4}}}
 Text(if(b.file.isEmpty())"Banque ${'A'+selected} vide" else b.name,color=bone,fontWeight=FontWeight.Bold)
 Row(horizontalArrangement=Arrangement.spacedBy(5.dp)){Pad("IMPORT WAV",false,Modifier.weight(1f)){if(b.file.isEmpty())picker.launch(arrayOf("audio/*","application/octet-stream")) else confirm="import"};Pad("VIDER",false,Modifier.weight(1f)){if(b.file.isNotEmpty())confirm="clear"}}
 if(b.file.isNotEmpty()){
 Text("${"%.2f".format(duration)} s • BPM original ${b.bpm}",fontSize=12.sp)
 Canvas(Modifier.fillMaxWidth().height(104.dp).background(Color(0xff20090b))){for(i in 0..7){val left=size.width*i/8;val width=size.width/8; if(b.mask and (1 shl i)==0)drawRect(Color(0xff55504a).copy(alpha=.45f),Offset(left,0f),androidx.compose.ui.geometry.Size(width,size.height));drawLine(bone.copy(alpha=.4f),Offset(left,0f),Offset(left,size.height))};peaks.forEachIndexed{i,p->val x=i*size.width/peaks.size;val idx=i*8/peaks.size;drawLine(if(b.mask and (1 shl idx)!=0)red else Color.Gray,Offset(x,size.height*(.5f-p*.45f)),Offset(x,size.height*(.5f+p*.45f)),2f)}}
 Text("SLICES • couper / réactiver",color=bone,fontSize=12.sp)
 for(group in (0..7).chunked(4)){Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(4.dp)){group.forEach{i->Pad("${i+1}",b.mask and (1 shl i)!=0,Modifier.weight(1f)){update(b.copy(mask=b.mask xor (1 shl i)))}}}}
 Row(horizontalArrangement=Arrangement.spacedBy(5.dp)){Pad("LOOP",b.loop,Modifier.weight(1f)){update(b.copy(loop=true))};Pad("ONE SHOT",!b.loop,Modifier.weight(1f)){update(b.copy(loop=false))}}
 Row(verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(5.dp)){Pad("−",false,Modifier.width(48.dp)){update(b.copy(bpm=(b.bpm-1).coerceAtLeast(40)))};Text("${b.bpm} BPM",color=red,modifier=Modifier.weight(1f));Pad("+",false,Modifier.width(48.dp)){update(b.copy(bpm=(b.bpm+1).coerceAtMost(300)))}}
 Text("BPM descriptif • pas de time-stretch",fontSize=11.sp)
 Row(horizontalArrangement=Arrangement.spacedBy(5.dp)){Pad("PLAY",player!=null,Modifier.weight(1f)){stop();busy=true;scope.launch{try{val file=withContext(Dispatchers.IO){val w=mutedSlices(store.wave(b),b.mask);File(context.cacheDir,"bank_preview.wav").apply{writeBytes(w.export(0,w.frames))}};val p=MediaPlayer();player=p;p.setDataSource(file.absolutePath);p.isLooping=b.loop;p.prepare();p.setOnCompletionListener{if(player===it)stop()};p.start();msg="Préécoute locale"}catch(e:Exception){stop();msg=e.message?:"Lecture impossible"}finally{busy=false}}};Pad("STOP",false,Modifier.weight(1f)){stop()}}
 Pad("EXPORTER WAV AVEC SLICES",false,Modifier.fillMaxWidth()){busy=true;scope.launch{try{pending=withContext(Dispatchers.IO){val w=mutedSlices(store.wave(b),b.mask);w.export(0,w.frames)};exporter.launch("moktek_bank_${'A'+selected}.wav")}catch(e:Exception){msg=e.message?:"Export impossible"}finally{busy=false}}}
 Text("COPIER / ÉCHANGER VERS",color=bone,fontSize=12.sp)
 Row(horizontalArrangement=Arrangement.spacedBy(5.dp)){(0..3).filter{it!=selected}.forEach{i->Pad("${'A'+i}",target==i,Modifier.weight(1f)){target=i}}}
 Row(horizontalArrangement=Arrangement.spacedBy(5.dp)){Pad("COPIER",false,Modifier.weight(1f)){if(banks[target].file.isNotEmpty())confirm="copy" else save(banks.toMutableList().apply{set(target,b)},"Banque copiée")};Pad("ÉCHANGER",false,Modifier.weight(1f)){save(banks.toMutableList().apply{set(selected,banks[target]);set(target,b)},"Banques échangées")}}
 }
 if(busy)LinearProgressIndicator(Modifier.fillMaxWidth());Text(msg,color=bone,fontSize=12.sp)
 if(confirm.isNotEmpty())AlertDialog(onDismissRequest={confirm=""},title={Text("Confirmer")},text={Text(if(confirm=="import")"Remplacer le sample de cette banque ?" else if(confirm=="copy")"Remplacer la banque ${'A'+target} ?" else "Vider cette banque locale ?")},confirmButton={TextButton(onClick={val action=confirm;confirm="";when(action){"import"->picker.launch(arrayOf("audio/*","application/octet-stream"));"copy"->save(banks.toMutableList().apply{set(target,b)},"Banque copiée");"clear"->update(Bank())}}){Text("CONFIRMER")}},dismissButton={TextButton(onClick={confirm=""}){Text("ANNULER")}})
}
