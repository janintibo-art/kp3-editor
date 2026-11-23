package org.moktek.kaoss

import android.content.Context
import org.json.JSONObject
import org.json.JSONArray
import java.io.*
import java.security.MessageDigest
import java.util.zip.ZipEntry
import java.util.zip.ZipInputStream
import java.util.zip.ZipOutputStream
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.sp

/** Project transport only; contains no Korg hardware commands. */
internal object CommonProjectV16 {
 private const val MAX_TOTAL=192L*1024*1024
 private const val MAX_FILE=48L*1024*1024
 private const val PROJECT="metadata/project-v16.json"
 private fun sha(b:ByteArray)=MessageDigest.getInstance("SHA-256").digest(b).joinToString(""){"%02x".format(it.toInt() and 255)}
 private fun read(input:InputStream,max:Long):ByteArray {
  val out=ByteArrayOutputStream();val buf=ByteArray(8192)
  while(true){val n=input.read(buf);if(n<0)break;require(out.size().toLong()+n<=max){"Fichier trop volumineux"};out.write(buf,0,n)}
  return out.toByteArray()
 }
 private val wavSlot=Regex("audio/[ABCD][0-7]\\.wav")
 private val jsonMeta=Regex("metadata/[a-zA-Z0-9._-]+\\.json")
 fun unpack(data:ByteArray):Map<String,ByteArray> {
  require(data.size.toLong()<=MAX_TOTAL){"Archive trop volumineuse"}
  val files=linkedMapOf<String,ByteArray>();var total=0L
  ZipInputStream(ByteArrayInputStream(data)).use{zip->while(true){val e=zip.nextEntry?:break;val path=e.name
   require(!e.isDirectory && (path=="manifest.json" || wavSlot.matches(path) || jsonMeta.matches(path)) && !files.containsKey(path) && files.size<70){"Entrée ZIP interdite : $path"}
   val bytes=read(zip,MAX_FILE);total+=bytes.size;require(total<=MAX_TOTAL){"ZIP trop volumineux"};files[path]=bytes;zip.closeEntry()
  }}
  val manifest=JSONObject(String(files["manifest.json"]?:error("Manifest absent"),Charsets.UTF_8))
  require(manifest.optString("format")=="moktek-exchange" && manifest.optInt("version")==1 && manifest.optBoolean("hardwareWrite",false)==false){"Archive incompatible"}
  val hashes=manifest.getJSONObject("files")
  require(hashes.length()==files.size-1){"Fichiers ajoutés ou manquants"}
  for((path,bytes) in files)if(path!="manifest.json")require(hashes.optString(path)==sha(bytes)){"Empreinte SHA-256 incorrecte : $path"}
  require((0 until hashes.length()).all{files.containsKey(hashes.names()!!.getString(it))}){"Inventaire ZIP incorrect"}
  return files
 }
 fun inspect(data:ByteArray):String {
  val files=unpack(data)
  val j=JSONObject(String(files[PROJECT]?:error("Projet V16 absent"),Charsets.UTF_8))
  require(j.optString("format")=="moktek-common-project-v1" && j.optInt("version")==1 && !j.optBoolean("hardwareWrite",true)){"Projet inconnu"}
  require(j.optString("title").length in 1..80){"Nom de projet invalide"}
  files["metadata/portable-pattern.json"]?.let { PortablePatternV14.inspect(data) }
  files["metadata/portable-synth.json"]?.let { PortableSynthV15.validate(JSONObject(String(it,Charsets.UTF_8))) }
  files.filterKeys{wavSlot.matches(it)}.forEach{(_,bytes)->
   require(bytes.size>=44 && String(bytes,0,4,Charsets.US_ASCII)=="RIFF" && String(bytes,8,4,Charsets.US_ASCII)=="WAVE") {"WAV incompatible"}
  }
  return "${j.getString("title")} • ${files.keys.count{wavSlot.matches(it)}} WAV • pattern : ${files.containsKey("metadata/portable-pattern.json")} • preset : ${files.containsKey("metadata/portable-synth.json")}."
 }
 fun importSamples(context:Context,data:ByteArray):String {
  inspect(data)
  // Existing importer verifies hash and PCM 16-bit and adds reference WAV without overwriting.
  return ProjectExchangeV13.importArchive(context,data)
 }
 fun importPattern(context:Context,data:ByteArray):String {
  inspect(data)
  return PortablePatternV14.apply(context,PortablePatternV14.inspect(data))
 }
 fun importPreset(context:Context,data:ByteArray):String {
  val files=unpack(data);inspect(data)
  val entry=files["metadata/portable-synth.json"]?:error("Aucun preset dans ce projet")
  val id=PortableSynthV15.save(context,JSONObject(String(entry,Charsets.UTF_8)))
  return "Preset ajouté sans écrasement : $id"
 }
 fun export(context:Context,title:String):ByteArray {
  require(title.length in 1..80){"Titre requis (80 caractères maximum)"}
  val files=linkedMapOf<String,ByteArray>()
  // Reuse the proven local backup, but map only explicitly named slots.
  val backup=KorgFileStore(context).createBackup()
  ZipInputStream(ByteArrayInputStream(backup)).use{zip->while(true){val e=zip.nextEntry?:break
   val match=Regex("banks/([ABCD][0-7])\\.wav").matchEntire(e.name)
   if(match!=null){val path="audio/${match.groupValues[1]}.wav";files[path]=read(zip,MAX_FILE)}
   zip.closeEntry()
  }}
  // A saved Android grid can be represented as the portable six-track pattern.
  runCatching{val patternZip=PortablePatternV14.exportSaved(context)
   val p=unpack(patternZip)["metadata/portable-pattern.json"]
   if(p!=null)files["metadata/portable-pattern.json"]=p
  }
  val custom=PortableSynthV15.list(context).firstOrNull()?.second
  if(custom!=null)files["metadata/portable-synth.json"]=custom.toString().toByteArray(Charsets.UTF_8)
  files[PROJECT]=JSONObject().put("format","moktek-common-project-v1").put("version",1).put("title",title).put("origin","android").put("hardwareWrite",false)
   .put("notice","Seuls les WAV aux slots nommés A0–D7 sont intégrés ; un preset personnalisé au maximum.").toString().toByteArray(Charsets.UTF_8)
  require(files.values.sumOf{it.size.toLong()}<=MAX_TOTAL){"Projet trop grand"}
  val hashes=JSONObject();files.forEach{(name,bytes)->hashes.put(name,sha(bytes))}
  val manifest=JSONObject().put("format","moktek-exchange").put("version",1).put("origin","android").put("hardwareWrite",false).put("files",hashes)
  return ByteArrayOutputStream().also{out->ZipOutputStream(out).use{zip->
   for((path,bytes) in files+mapOf("manifest.json" to manifest.toString().toByteArray(Charsets.UTF_8))){zip.putNextEntry(ZipEntry(path));zip.write(bytes);zip.closeEntry()}
  }}.toByteArray()
 }
}

@Composable internal fun CommonProjectPanelV16() {
 val ctx=LocalContext.current
 var note by remember{mutableStateOf("Archive de projet locale, sans transfert Korg.")}
 var candidate by remember{mutableStateOf<ByteArray?>(null)}
 var pending by remember{mutableStateOf<ByteArray?>(null)}
 var title by remember{mutableStateOf("Mon projet mokteK")}
 val select=rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()){uri->if(uri!=null){
  runCatching{ctx.contentResolver.openInputStream(uri)?.use{stream->
   val out=ByteArrayOutputStream();val buf=ByteArray(8192)
   while(true){val n=stream.read(buf);if(n<0)break;require(out.size().toLong()+n<=192L*1024*1024){"ZIP trop volumineux"};out.write(buf,0,n)};out.toByteArray()
  }?:error("Fichier inaccessible")}.onSuccess{bytes->runCatching{note=CommonProjectV16.inspect(bytes);candidate=bytes}.onFailure{note=it.message?:"Fichier incompatible"}}
    .onFailure{note=it.message?:"Fichier inaccessible"}
 }}
 val save=rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/zip")){uri->val bytes=pending;pending=null;if(uri!=null&&bytes!=null){
  runCatching{ctx.contentResolver.openOutputStream(uri)?.use{it.write(bytes)}?:error("Écriture impossible")}
   .onSuccess{note="Projet V16 exporté"}.onFailure{note=it.message?:"Erreur export"}
 }}
 HorizontalDivider()
 Text("V16 • PROJET COMMUN WINDOWS ↔ ANDROID",color=Color(0xffff493e),fontSize=16.sp)
 Text("Les importations sont séparées. Les banques existantes sont conservées ; le pattern demande une confirmation explicite.",fontSize=12.sp)
 OutlinedTextField(value=title,onValueChange={title=it.take(80)},label={Text("Nom du projet")})
 OutlinedButton(onClick={runCatching{pending=CommonProjectV16.export(ctx,title);save.launch("moktek_projet_v16.zip")}.onFailure{note=it.message?:"Erreur"}}){Text("EXPORTER PROJET V16")}
 OutlinedButton(onClick={select.launch(arrayOf("application/zip","application/octet-stream"))}){Text("OUVRIR PROJET V16")}
 Text(note,fontSize=12.sp)
 candidate?.let{bytes->
  OutlinedButton(onClick={runCatching{note=CommonProjectV16.importSamples(ctx,bytes)}.onFailure{note=it.message?:"Erreur WAV"}}){Text("AJOUTER LES WAV (SANS REMPLACER)")}
  OutlinedButton(onClick={runCatching{note=CommonProjectV16.importPreset(ctx,bytes)}.onFailure{note=it.message?:"Aucun preset"}}){Text("AJOUTER LE PRESET")}
  var confirm by remember{mutableStateOf(false)}
  OutlinedButton(onClick={confirm=true}){Text("IMPORTER LE PATTERN (CONFIRMATION)")}
  if(confirm)AlertDialog(onDismissRequest={confirm=false},title={Text("Remplacer le pattern SEQ sauvegardé ?")},
   text={Text("Une copie de secours du pattern actuel sera créée. Aucun envoi au matériel Korg.")},
   confirmButton={TextButton(onClick={confirm=false;runCatching{note=CommonProjectV16.importPattern(ctx,bytes)}.onFailure{note=it.message?:"Erreur pattern"}}){Text("CONFIRMER")}},
   dismissButton={TextButton(onClick={confirm=false}){Text("ANNULER")}})
 }
}
