package org.moktek.kaoss

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.*
import java.security.MessageDigest
import java.util.zip.ZipEntry
import java.util.zip.ZipInputStream
import java.util.zip.ZipOutputStream

/** A V14 archive is our own format, NOT Korg's proprietary All Data format. */
internal class KorgFileStore(private val context: Context) {
 private val korgDir = File(context.filesDir, "korg_reference_v14").apply { mkdirs() }
 private val bankDir = File(context.filesDir, "banks_v11")
 private val prefNames = listOf("native_sessions", "banks_v11", "patterns_v9", "synth_presets")
 private val legacyPrefNames = listOf("native_sessions", "banks_v11")
 private val maxSingle = 48L * 1024 * 1024
 private val maxTotal = 192L * 1024 * 1024

 private fun digest(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it.toInt() and 255) }
 private fun safeName(name: String): String = name.replace(Regex("[^a-zA-Z0-9._-]"), "_").take(90).trim('.').ifEmpty { "file" }
 private fun extension(name: String): String = name.substringAfterLast('.', "").lowercase()
 private val supported = setOf("wav", "aif", "aiff", "kps", "kpg", "kpa", "p3s", "p3g", "p3a")

 data class Reference(val name: String, val bytes: Long, val sha256: String)
 fun references(): List<Reference> = korgDir.listFiles().orEmpty().filter { it.isFile }.sortedBy { it.name }.map { Reference(it.name, it.length(), FileInputStream(it).use { ins -> hash(ins) }) }
 private fun hash(input: InputStream): String {
  val md = MessageDigest.getInstance("SHA-256")
  val buf = ByteArray(8192)
  while (true) { val n=input.read(buf); if(n<0)break; md.update(buf,0,n) }
  return md.digest().joinToString("") { "%02x".format(it.toInt() and 255) }
 }
 private fun readLimited(stream: InputStream, limit: Long): ByteArray {
  val out = ByteArrayOutputStream(); val buf=ByteArray(8192); var total=0L
  while(true) { val n=stream.read(buf); if(n<0)break; total+=n; require(total<=limit){"Fichier trop volumineux (limite ${limit/1048576} Mio)"};out.write(buf,0,n) }
  return out.toByteArray()
 }
 fun addReference(uri: Uri): Reference {
  val resolver=context.contentResolver
  val original=resolver.query(uri,arrayOf(OpenableColumns.DISPLAY_NAME),null,null,null)?.use { c -> if(c.moveToFirst())c.getString(0) else null } ?: "unknown.bin"
  val sanitized=safeName(original)
  require(extension(sanitized) in supported) { "Extension non prise en charge : $sanitized" }
  val bytes=resolver.openInputStream(uri)?.use { readLimited(it,maxSingle) } ?: error("Fichier inaccessible")
  require(bytes.isNotEmpty()){ "Fichier vide" }
  val sum=digest(bytes)
  val base=sanitized.substringBeforeLast('.',sanitized); val ext=sanitized.substringAfterLast('.',"")
  var name=sanitized;var counter=1
  while(File(korgDir,name).exists()){name="${base.take(60)}_${counter++}.$ext"}
  val target=File(korgDir,name);target.writeBytes(bytes)
  return Reference(name,bytes.size.toLong(),sum)
 }
 fun readReference(name: String): ByteArray {
  require(name==safeName(name) && extension(name) in supported){"Nom invalide"}
  val file=File(korgDir,name);require(file.isFile){"Fichier introuvable"}
  return file.inputStream().use { readLimited(it,maxSingle) }
 }
 fun createBackup(): ByteArray {
  val out=ByteArrayOutputStream()
  val manifest=JSONObject().put("format","moktek-backup").put("version",2).put("modelScope","LOCAL_ONLY").put("created",System.currentTimeMillis())
  val files=JSONObject();var total=0L
  ZipOutputStream(out).use { zip ->
   fun put(path:String,bytes:ByteArray) { total+=bytes.size;require(total<=maxTotal){"Sauvegarde trop volumineuse"};zip.putNextEntry(ZipEntry(path));zip.write(bytes);zip.closeEntry();files.put(path,digest(bytes)) }
   prefNames.forEach { name ->
    val obj=JSONObject();context.getSharedPreferences(name,Context.MODE_PRIVATE).all.forEach { (k,v) ->
     when(v){ is String -> obj.put(k, JSONObject().put("type","string").put("value",v))
      is Int -> obj.put(k, JSONObject().put("type","int").put("value",v))
      is Long -> obj.put(k, JSONObject().put("type","long").put("value",v))
      is Boolean -> obj.put(k, JSONObject().put("type","boolean").put("value",v))
      is Float -> obj.put(k, JSONObject().put("type","float").put("value",v.toDouble())) }
    }
    put("prefs/$name.json",obj.toString().toByteArray(Charsets.UTF_8))
   }
   if(bankDir.isDirectory)bankDir.listFiles().orEmpty().filter{it.isFile && it.name.matches(Regex("[a-zA-Z0-9._-]+\\.wav"))}.forEach { f ->
    require(f.length()<=maxSingle){"Sample trop volumineux : ${f.name}"};put("banks/${f.name}",f.readBytes())
   }
   korgDir.listFiles().orEmpty().filter{it.isFile && extension(it.name) in supported}.forEach { f ->
    require(f.length()<=maxSingle){"Fichier Korg trop volumineux"};put("reference/${f.name}",f.readBytes())
   }
   manifest.put("files",files)
   zip.putNextEntry(ZipEntry("manifest.json"));zip.write(manifest.toString(2).toByteArray(Charsets.UTF_8));zip.closeEntry()
  }
  return out.toByteArray()
 }
 private fun decodeBackup(data:ByteArray): Map<String,ByteArray>{
  val items=linkedMapOf<String,ByteArray>();var total=0L
  ZipInputStream(ByteArrayInputStream(data)).use { zip ->
   while(true){val entry=zip.nextEntry ?: break;val path=entry.name
    require(!entry.isDirectory && !path.contains("..") && !path.startsWith("/") && !path.contains('\\')){"Archive non conforme"}
    require(path=="manifest.json" || path in prefNames.map{"prefs/$it.json"} || (path.startsWith("banks/") && path.removePrefix("banks/").matches(Regex("[a-zA-Z0-9._-]+\\.wav"))) || (path.startsWith("reference/") && path.removePrefix("reference/")==safeName(path.removePrefix("reference/")) && extension(path) in supported)){"Entrée non reconnue : $path"}
    require(!items.containsKey(path)){"Entrée dupliquée"}
    val bytes=readLimited(zip,maxSingle);total+=bytes.size;require(total<=maxTotal){"Archive trop volumineuse"};items[path]=bytes;zip.closeEntry()
   }
  }
  val manifest=JSONObject(String(items["manifest.json"]?:error("Manifest absent"),Charsets.UTF_8))
  require(manifest.optString("format")=="moktek-backup" && manifest.optInt("version") in 1..2){"Format de sauvegarde incompatible"}
  val entries=manifest.getJSONObject("files")
  require(entries.length()==items.size-1){"Fichiers manquants ou ajoutés"}
  for((path,bytes) in items){if(path!="manifest.json")require(entries.optString(path)==digest(bytes)){"Empreinte invalide : $path"}}
  val required=if(manifest.optInt("version")==1)legacyPrefNames else prefNames
  required.forEach { name->JSONObject(String(items["prefs/$name.json"]?:error("Préférences manquantes"),Charsets.UTF_8)) }
  return items
 }
 fun backupAudit():String {
  val names=mapOf("native_sessions" to "Sessions et mémoires", "banks_v11" to "Banques A–D", "patterns_v9" to "Séquenceur", "synth_presets" to "Presets Synth Factory")
  val entries=names.map { (k,label)-> "$label : ${context.getSharedPreferences(k,Context.MODE_PRIVATE).all.size} réglage(s)" }
  val wav=bankDir.listFiles().orEmpty().count { it.isFile && it.extension.lowercase()=="wav" }
  val refs=korgDir.listFiles().orEmpty().count { it.isFile }
  return (entries+"Samples WAV : $wav"+"Fichiers de référence : $refs").joinToString("\n")
 }
 fun verifyBackup(data:ByteArray):String = describeBackup(data)
 fun describeBackup(data:ByteArray):String{
  val items=decodeBackup(data)
  return "Sauvegarde locale valide : ${items.keys.count{it.startsWith("banks/")}} WAV, ${items.keys.count{it.startsWith("reference/")}} fichiers Korg conservés. La restauration remplace les banques et réglages locaux, pas le contenu physique du KP3."
 }
 fun restoreBackup(data:ByteArray){
  val files=decodeBackup(data)
  // Save a recovery point first, before touching any current data.
  val recovery=File(context.filesDir,"moktek_recovery_before_v14_restore.zip")
  recovery.writeBytes(createBackup())
  val stage=File(context.cacheDir,"moktek_restore_stage");stage.deleteRecursively();stage.mkdirs()
  try {
   files.filterKeys { it.startsWith("banks/") || it.startsWith("reference/") }.forEach { (path,bytes)->
    val dest=File(stage,path);dest.parentFile?.mkdirs();dest.writeBytes(bytes)
   }
   bankDir.mkdirs();korgDir.mkdirs()
   files.filterKeys{it.startsWith("banks/")}.forEach{(path,bytes)->File(bankDir,path.substringAfter('/')).writeBytes(bytes)}
   files.filterKeys{it.startsWith("reference/")}.forEach{(path,bytes)->File(korgDir,path.substringAfter('/')).writeBytes(bytes)}
   prefNames.forEach { name ->
    val raw=files["prefs/$name.json"] ?: return@forEach // Archive V14 ancienne : préserver les nouveaux réglages
    val j=JSONObject(String(raw,Charsets.UTF_8))
    val edit=context.getSharedPreferences(name,Context.MODE_PRIVATE).edit().clear()
    j.keys().forEach { k->
     val entry=j.get(k)
     if(entry is JSONObject){
      when(entry.optString("type")) {
       "string" -> edit.putString(k,entry.getString("value"))
       "int" -> edit.putInt(k,entry.getInt("value"))
       "long" -> edit.putLong(k,entry.getLong("value"))
       "float" -> edit.putFloat(k,entry.getDouble("value").toFloat())
       "boolean" -> edit.putBoolean(k,entry.getBoolean("value"))
       else -> error("Type de préférence inconnu : $k")
      }
     }else edit.putString(k,j.getString(k)) // Sauvegarde historique V14
    }
    check(edit.commit()){ "Impossible de restaurer $name" }
   }
  } finally {stage.deleteRecursively()}
 }
}

@Composable internal fun KorgFileCenter() {
 val ctx=LocalContext.current;val store=remember{KorgFileStore(ctx)};val scope=rememberCoroutineScope()
 val red=Color(0xffff493e);val bone=Color(0xffe9dac2);val steel=Color(0xff83705e)
 var message by remember{mutableStateOf("Gestion locale uniquement • aucun envoi au KP3")}
 var refs by remember{mutableStateOf(store.references())}
 var selected by remember{mutableStateOf("")}
 var busy by remember{mutableStateOf(false)}
 var pending by remember{mutableStateOf<ByteArray?>(null)}
 var backupToRestore by remember{mutableStateOf<ByteArray?>(null)}
 var confirmation by remember{mutableStateOf(false)}
 fun runTask(block:suspend ()->Unit){scope.launch{busy=true;try{block()}catch(e:Exception){message=e.message?:"Erreur"}finally{busy=false}}}
 val export=rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/zip")){uri->val data=pending;pending=null;if(uri!=null&&data!=null)runTask{withContext(Dispatchers.IO){ctx.contentResolver.openOutputStream(uri,"wt")?.use{it.write(data)}?:error("Écriture impossible")};message="Sauvegarde ZIP exportée"}}
 val originalExport=rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/octet-stream")){uri->val name=selected;if(uri!=null&&name.isNotBlank())runTask{withContext(Dispatchers.IO){val bytes=store.readReference(name);ctx.contentResolver.openOutputStream(uri,"wt")?.use{it.write(bytes)}?:error("Écriture impossible")};message="Copie identique exportée : $name"}}
 val filePicker=rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()){uri->if(uri!=null)runTask{val ref=withContext(Dispatchers.IO){store.addReference(uri)};refs=withContext(Dispatchers.IO){store.references()};selected=ref.name;message="Fichier conservé sans modification : ${ref.name}"}}
 val restorePicker=rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()){uri->if(uri!=null)runTask{val data=withContext(Dispatchers.IO){ctx.contentResolver.openInputStream(uri)?.use { inp -> val out=ByteArrayOutputStream();val buffer=ByteArray(8192);while(true){val n=inp.read(buffer);if(n<0)break;require(out.size()+n<=200*1048576){"ZIP trop volumineux"};out.write(buffer,0,n)};out.toByteArray() }?:error("Archive inaccessible")};message=withContext(Dispatchers.IO){store.describeBackup(data)};backupToRestore=data;confirmation=true}}
 @Composable fun Control(label:String, action:()->Unit){Box(Modifier.fillMaxWidth().heightIn(min=46.dp).border(1.dp,steel,RoundedCornerShape(5.dp)).background(Color(0xff34251e)).clickable(enabled=!busy,onClick=action).padding(12.dp),contentAlignment=Alignment.Center){Text(label,color=bone,fontWeight=FontWeight.Bold,fontSize=12.sp)}}
 Text("KORG FILE CENTER",color=red,fontSize=22.sp,fontWeight=FontWeight.Bold)
 Text("KP3 / KP3+ • fichiers et sauvegardes",color=bone,fontSize=12.sp)
 Text("COPIE SÉCURISÉE DES FICHIERS",color=red,fontWeight=FontWeight.Bold,fontSize=13.sp)
 Text("Importer des fichiers WAV / AIFF ou fichiers natifs Korg en conservant leurs octets à l'identique. Leur contenu propriétaire n'est pas encore décodé.",color=bone,fontSize=12.sp)
 Control("IMPORTER UN FICHIER KORG / AUDIO") {filePicker.launch(arrayOf("*/*"))}
 refs.forEach { ref->
  Column(Modifier.fillMaxWidth().border(1.dp,if(selected==ref.name)red else steel,RoundedCornerShape(5.dp)).clickable{selected=ref.name}.padding(9.dp)){
   Text(ref.name,color=bone,fontWeight=FontWeight.Bold,fontSize=12.sp)
   Text("${ref.bytes} octets • SHA-256 ${ref.sha256.take(16)}…",color=bone,fontSize=10.sp)
  }
 }
 if(selected.isNotBlank())Control("EXPORTER LE FICHIER ORIGINAL") {originalExport.launch(selected)}
 HorizontalDivider(color=steel)
 Text("SAUVEGARDE mokteK",color=red,fontWeight=FontWeight.Bold,fontSize=14.sp)
 Text("Archive ZIP des banques A–D, sessions, mémoires, séquenceur et presets Synth Factory, plus fichiers Korg importés. Ce n’est PAS un fichier All Data chargeable sur un KP3.",color=bone,fontSize=12.sp)
 Text("INVENTAIRE AVANT SAUVEGARDE",color=red,fontSize=13.sp,fontWeight=FontWeight.Bold)
 Text(store.backupAudit(),color=bone,fontSize=12.sp)
 Control("EXPORTER MA SAUVEGARDE ZIP") {runTask {pending=withContext(Dispatchers.IO){store.createBackup().also{store.verifyBackup(it)}};message="Archive contrôlée : empreintes SHA-256 vérifiées";export.launch("moktek_backup_v16.zip")}}
 Control("IMPORTER / RESTAURER UNE SAUVEGARDE") {restorePicker.launch(arrayOf("application/zip","application/octet-stream"))}
 Control("EXPORTER LA COPIE DE SECOURS") {runTask { val saved=withContext(Dispatchers.IO){File(ctx.filesDir,"moktek_recovery_before_v14_restore.zip").takeIf{it.isFile}?.readBytes() ?: error("Aucune restauration précédente")};pending=saved;export.launch("moktek_recuperation_v14.zip") }}
 if(busy)LinearProgressIndicator(Modifier.fillMaxWidth())
 Text(message,color=bone,fontSize=12.sp)
 Text("V16 : une sauvegarde locale vérifiée par empreintes SHA-256, compatible avec les sauvegardes V14. Aucune opération d'écriture sur KP3/KP3+.",color=bone,fontSize=11.sp)
 Text("Avant toute restauration, une copie de sécurité est créée dans les fichiers privés de l'application. Fermer et rouvrir l'application après restauration.",color=bone,fontSize=11.sp)
 if(confirmation)AlertDialog(onDismissRequest={confirmation=false;backupToRestore=null},title={Text("REMPLACER LES DONNÉES LOCALES ?")},text={Text("Les sessions et réglages actuels seront remplacés. Une copie de secours locale est créée avant restauration. AUCUNE donnée du KP3 physique ne sera modifiée.")},confirmButton={TextButton(onClick={val data=backupToRestore;backupToRestore=null;confirmation=false;if(data!=null)runTask{withContext(Dispatchers.IO){store.restoreBackup(data)};refs=store.references();message="Restauration terminée. Redémarrer l'application."}}){Text("RESTAURER")}},dismissButton={TextButton(onClick={confirmation=false;backupToRestore=null}){Text("ANNULER")}})
}
