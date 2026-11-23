package org.moktek.kaoss

import android.content.Context
import org.json.JSONObject
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.security.MessageDigest
import java.util.UUID
import java.util.zip.ZipEntry
import java.util.zip.ZipInputStream
import java.util.zip.ZipOutputStream
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** Portable synth presets only. Nothing is transmitted to Korg hardware. */
internal object PortableSynthV15 {
 private const val PATH="metadata/portable-synth.json"
 private val kinds=setOf("Kick","Bass","Zap","Lead","Noise","Sine","Acid","Snare","Hat","Tom")
 private fun sha(bytes:ByteArray)=MessageDigest.getInstance("SHA-256").digest(bytes).joinToString(""){"%02x".format(it.toInt() and 255)}
 private fun num(j:JSONObject,key:String,lo:Double,hi:Double):Double {
  val raw=j.get(key);require(raw is Number){"Valeur numérique attendue : $key"}
  val v=raw.toDouble();require(!v.isNaN() && !v.isInfinite() && v>=lo && v<=hi){"Valeur invalide : $key"};return v
 }
 fun validate(j:JSONObject):JSONObject {
  require(j.optString("format")=="moktek-portable-synth-v1"){"Format de preset incompatible"}
  require(j.getString("kind") in kinds){"Moteur inconnu"}
  require(j.getString("name").length in 1..80){"Nom de preset invalide"}
  val bpm=j.get("bpm");require(bpm is Int && bpm in 70..240){"BPM invalide"}
  num(j,"pitch",25.0,1800.0);num(j,"decay",.02,4.0);num(j,"drive",0.0,8.0)
  num(j,"tone",0.0,1.0);num(j,"volume",0.0,1.0)
  require(j.getString("origin") in setOf("android","windows")){"Origine inconnue"}
  return j
 }
 private fun readBounded(input:java.io.InputStream,max:Int):ByteArray {
  val out=ByteArrayOutputStream();val chunk=ByteArray(4096)
  while(true){val n=input.read(chunk);if(n<0)break;require(out.size()+n<=max){"Archive trop volumineuse"};out.write(chunk,0,n)}
  return out.toByteArray()
 }
 fun importZip(data:ByteArray):JSONObject {
  require(data.size<=65536){"Preset ZIP trop volumineux"}
  val entries=linkedMapOf<String,ByteArray>()
  ZipInputStream(ByteArrayInputStream(data)).use{zip->
   while(true){val e=zip.nextEntry?:break
    require(!e.isDirectory && e.name in setOf(PATH,"manifest.json") && !entries.containsKey(e.name) && entries.size<2){"Entrée ZIP interdite"}
    entries[e.name]=readBounded(zip,32768);zip.closeEntry()
   }
  }
  require(entries.keys==setOf(PATH,"manifest.json")){"Fichiers ZIP manquants"}
  val manifest=JSONObject(String(entries["manifest.json"]!!,Charsets.UTF_8))
  require(manifest.optString("format")=="moktek-exchange" && manifest.optInt("version")==1){"Manifest invalide"}
  val files=manifest.getJSONObject("files");require(files.length()==1 && files.optString(PATH)==sha(entries[PATH]!!)){"SHA-256 invalide"}
  return validate(JSONObject(String(entries[PATH]!!,Charsets.UTF_8)))
 }
 fun exportZip(preset:JSONObject):ByteArray {
  val j=validate(JSONObject(preset.toString()));val data=j.toString().toByteArray(Charsets.UTF_8)
  val manifest=JSONObject().put("format","moktek-exchange").put("version",1).put("origin","android").put("hardwareWrite",false).put("files",JSONObject().put(PATH,sha(data)))
  return ByteArrayOutputStream().also{out->ZipOutputStream(out).use{zip->
   for((path,bytes) in listOf(PATH to data,"manifest.json" to manifest.toString().toByteArray(Charsets.UTF_8))){zip.putNextEntry(ZipEntry(path));zip.write(bytes);zip.closeEntry()}
  }}.toByteArray()
 }
 fun toAndroid(j:JSONObject):JSONObject {
  validate(j)
  val fallback=mapOf("Zap" to "Tom","Lead" to "Acid","Noise" to "Snare","Sine" to "Bass")
  val kind=fallback[j.getString("kind")] ?: j.getString("kind")
  val drive=j.getDouble("drive")
  return JSONObject().put("format","moktek-portable-synth-v1").put("origin","android")
   .put("name",j.getString("name")).put("kind",kind).put("bpm",j.getInt("bpm"))
   .put("pitch",j.getDouble("pitch").coerceIn(25.0,400.0))
   .put("decay",j.getDouble("decay").coerceIn(.02,.5))
   .put("drive",(if(j.getString("origin")=="windows")1.0+drive*7 else drive).coerceIn(1.0,8.0))
   .put("tone",j.getDouble("tone")).put("volume",j.getDouble("volume"))
 }
 fun save(context:Context,j:JSONObject):String {
  val usable=toAndroid(j)
  val prefs=context.getSharedPreferences("synth_presets",Context.MODE_PRIVATE)
  val id="portable_v15_"+UUID.randomUUID().toString()
  check(prefs.edit().putString(id,usable.toString()).commit()){"Impossible de sauvegarder le preset"}
  return id
 }
 fun list(context:Context):List<Pair<String,JSONObject>> {
  return context.getSharedPreferences("synth_presets",Context.MODE_PRIVATE).all
   .filterKeys{it.startsWith("portable_v15_")}.mapNotNull{(key,value)->
    runCatching{key to validate(JSONObject(value as String))}.getOrNull()
   }.sortedBy{it.second.optString("name")}
 }
 fun builtIn(p:SynthPreset):JSONObject=validate(JSONObject().put("format","moktek-portable-synth-v1")
  .put("origin","android").put("name",p.name).put("kind",p.kind).put("bpm",p.bpm)
  .put("pitch",p.pitch.toDouble()).put("decay",p.decay.toDouble()).put("drive",p.drive.toDouble())
  .put("tone",p.tone.toDouble()).put("volume",1.0))
 fun toWave(j:JSONObject):ByteArray {
  val p=toAndroid(j)
  val pcm=SynthFactory.render(44100,p.getInt("bpm"),p.getString("kind"),p.getDouble("pitch").toFloat(),
   p.getDouble("decay").toFloat(),p.getDouble("drive").toFloat(),p.getDouble("tone").toFloat())
  val head=ByteArrayOutputStream();val d=java.io.DataOutputStream(head)
  fun le(n:Int,size:Int){for(i in 0 until size)d.writeByte((n ushr (8*i)) and 255)}
  d.writeBytes("RIFF");le(36+pcm.size,4);d.writeBytes("WAVEfmt ");le(16,4);le(1,2);le(1,2)
  le(44100,4);le(88200,4);le(2,2);le(16,2);d.writeBytes("data");le(pcm.size,4);d.write(pcm)
  return head.toByteArray()
 }
}

@Composable internal fun PortableSynthPanelV15(){
 val ctx=LocalContext.current
 fun readMax(input:java.io.InputStream,limit:Int):ByteArray {
  val out=ByteArrayOutputStream();val chunk=ByteArray(4096)
  while(true){val n=input.read(chunk);if(n<0)break;require(out.size()+n<=limit){"ZIP trop volumineux"};out.write(chunk,0,n)}
  return out.toByteArray()
 }
 var status by remember {mutableStateOf("Presets locaux seulement • aucune écriture sur Korg")}
 var imported by remember {mutableStateOf<JSONObject?>(null)}
 var saved by remember {mutableStateOf(PortableSynthV15.list(ctx))}
 var selected by remember {mutableStateOf<JSONObject?>(null)}
 var pending by remember {mutableStateOf<ByteArray?>(null)}
 val picker=rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()){uri->if(uri!=null){
  runCatching{ctx.contentResolver.openInputStream(uri)?.use{PortableSynthV15.importZip(readMax(it,65537))}?:error("Fichier inaccessible")}
   .onSuccess{imported=it;status="Preset ${it.getString("name")} reconnu. Confirmez l'import."}
   .onFailure{status=it.message?:"Import impossible"}
 }}
 val zipExport=rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/zip")){uri->val data=pending;pending=null
  if(uri!=null&&data!=null)runCatching{ctx.contentResolver.openOutputStream(uri)?.use{it.write(data)}?:error("Écriture impossible")}
   .onSuccess{status="Preset ZIP exporté"}.onFailure{status=it.message?:"Export impossible"}
 }
 val wavExport=rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("audio/wav")){uri->val data=pending;pending=null
  if(uri!=null&&data!=null)runCatching{ctx.contentResolver.openOutputStream(uri)?.use{it.write(data)}?:error("Écriture impossible")}
   .onSuccess{status="WAV généré localement"}.onFailure{status=it.message?:"WAV impossible"}
 }
 HorizontalDivider()
 Text("V15 • SYNTH FACTORY • WINDOWS ↔ ANDROID",color=Color(0xffff493e),fontSize=16.sp)
 Text("Import/export de presets paramétriques. Le son peut différer selon le moteur. Exportez le WAV pour conserver exactement le son.",fontSize=12.sp)
 OutlinedButton(onClick={picker.launch(arrayOf("application/zip","application/octet-stream"))}){Text("IMPORTER PRESET WINDOWS ZIP")}
 Text("Presets Android intégrés",fontSize=13.sp)
 SynthFactory.presets.forEach{p->TextButton(onClick={selected=PortableSynthV15.builtIn(p);status="Sélection : ${p.name}"}){Text("• ${p.name}")}}
 Text("Presets importés (${saved.size})",fontSize=13.sp)
 saved.forEach{(_,p)->TextButton(onClick={selected=p;status="Sélection : ${p.getString("name")}"}){Text("• ${p.optString("name")}")}}
 selected?.let{preset->
  Text("Sélection : ${preset.optString("name")} / ${preset.optString("kind")}",fontSize=12.sp)
  OutlinedButton(onClick={runCatching{pending=PortableSynthV15.exportZip(preset);zipExport.launch("moktek_synth_v15.zip")}.onFailure{status=it.message?:"Erreur"}}){Text("EXPORTER CE PRESET POUR WINDOWS")}
  OutlinedButton(onClick={runCatching{pending=PortableSynthV15.toWave(preset);wavExport.launch("moktek_synth_v15.wav")}.onFailure{status=it.message?:"Erreur WAV"}}){Text("GÉNÉRER UN WAV SUR ANDROID")}
 }
 Text(status,fontSize=12.sp)
 if(imported!=null)AlertDialog(onDismissRequest={imported=null},title={Text("IMPORTER CE PRESET ?")},
  text={Text("Les paramètres seront adaptés au moteur Android ; le rendu audio peut différer. Le preset sera ajouté sans remplacer vos presets existants.")},
  confirmButton={TextButton(onClick={val j=imported;imported=null;if(j!=null)runCatching{PortableSynthV15.save(ctx,j)}.onSuccess{saved=PortableSynthV15.list(ctx);status="Preset importé (sans écrasement)"}.onFailure{status=it.message?:"Erreur"}}){Text("AJOUTER")}},
  dismissButton={TextButton(onClick={imported=null}){Text("ANNULER")}})
}
