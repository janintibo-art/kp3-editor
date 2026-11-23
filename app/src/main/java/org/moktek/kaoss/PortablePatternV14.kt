package org.moktek.kaoss

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.security.MessageDigest
import java.util.zip.ZipEntry
import java.util.zip.ZipInputStream
import java.util.zip.ZipOutputStream

/** Local pattern transfer only. Never sends MIDI or writes a Korg device. */
internal object PortablePatternV14 {
 private fun sha(b:ByteArray)=MessageDigest.getInstance("SHA-256").digest(b).joinToString(""){"%02x".format(it.toInt() and 255)}
 private fun verify(j:JSONObject):JSONObject {
  require(j.optString("format")=="moktek-portable-pattern-v1"){"Format pattern non reconnu"}
  val steps=j.getInt("steps");val bpm=j.getInt("bpm")
  require(steps in listOf(16,32,64) && bpm in 70..240){"Pas / BPM incompatibles"}
  val grid=j.getJSONArray("grid");val volumes=j.getJSONArray("volumes")
  require(grid.length()==6 && volumes.length()==6){"Six pistes nécessaires"}
  for(l in 0..5){
   val row=grid.getJSONArray(l);require(row.length()==steps){"Longueur de piste incorrecte"}
   for(n in 0 until steps)require(row.get(n) is Boolean){"Pas non booléen"}
   val v=volumes.getDouble(l);require(v.isFinite() && v in 0.0..1.0){"Volume incorrect"}
  }
  return j
 }
 fun inspect(data:ByteArray):JSONObject {
  require(data.size<=192*1024*1024){"Archive trop volumineuse"}
  val entries=linkedMapOf<String,ByteArray>();var total=0L
  ZipInputStream(ByteArrayInputStream(data)).use { zip->
   while(true){val entry=zip.nextEntry?:break;val name=entry.name
    require(!entry.isDirectory && name.length<=100 && !name.contains("..") && !name.contains('\\') && !name.startsWith('/')){"Chemin ZIP interdit"}
    require(entries.size<256 && !entries.containsKey(name)){"ZIP dupliqué ou trop grand"}
    val out=ByteArrayOutputStream();val buf=ByteArray(8192)
    while(true){val n=zip.read(buf);if(n<0)break;require(out.size().toLong()+n<=48L*1024*1024){"Entrée trop grande"};out.write(buf,0,n)}
    total+=out.size().toLong();require(total<=192L*1024*1024){"Contenu trop volumineux"}
    entries[name]=out.toByteArray();zip.closeEntry()
   }
  }
  val manifest=JSONObject(String(entries["manifest.json"]?:error("Manifest absent"),Charsets.UTF_8))
  require(manifest.optString("format")=="moktek-exchange" && manifest.optInt("version")==1){"Format ZIP incompatible"}
  val hashes=manifest.getJSONObject("files");require(hashes.length()==entries.size-1){"Inventaire invalide"}
  for((name,content) in entries)if(name!="manifest.json")require(hashes.optString(name)==sha(content)){"SHA-256 non conforme : $name"}
  require((0 until hashes.length()).all{entries.containsKey(hashes.names()!!.getString(it))}){"Fichier manquant"}
  return verify(JSONObject(String(entries["metadata/portable-pattern.json"]?:error("Aucun pattern V14 dans le ZIP"),Charsets.UTF_8)))
 }
 fun apply(context:Context,pattern:JSONObject):String {
  val j=verify(pattern);val prefs=context.getSharedPreferences("patterns_v9",Context.MODE_PRIVATE)
  // One recovery record, readable before committing anything.
  val previous=prefs.all
  val backup=JSONObject()
  for((key,value) in previous){when(value){is String->backup.put(key,JSONObject().put("type","string").put("value",value));is Int->backup.put(key,JSONObject().put("type","int").put("value",value))}}
  context.openFileOutput("pattern_before_v14.json",Context.MODE_PRIVATE).use{it.write(backup.toString().toByteArray())}
  val steps=j.getInt("steps");val grid=j.getJSONArray("grid");val bits=CharArray(384){'0'}
  for(l in 0..5){val row=grid.getJSONArray(l);for(s in 0 until steps)if(row.getBoolean(s))bits[l*64+s]='1'}
  val volumes=j.getJSONArray("volumes");val vol=(0..5).joinToString(","){volumes.getDouble(it).toString()}
  check(prefs.edit().putString("grid",String(bits)).putInt("steps",steps).putInt("bpm",j.getInt("bpm")).putString("vol",vol).commit()){"Échec sauvegarde Android"}
  return "Pattern V14 importé : 6 pistes, $steps pas, ${j.getInt("bpm")} BPM. Redémarrer l'application, puis SEQ > CHARGER. Ancien pattern conservé en copie de secours."
 }
 fun exportSaved(context:Context):ByteArray {
  val prefs=context.getSharedPreferences("patterns_v9",Context.MODE_PRIVATE)
  val bits=prefs.getString("grid",null)?:error("Sauvegardez un pattern dans SEQ avant l'export")
  require(bits.length==384 && bits.all{it=='0'||it=='1'}){"Grille Android non valide"}
  val steps=prefs.getInt("steps",16);val bpm=prefs.getInt("bpm",174)
  require(steps in listOf(16,32,64) && bpm in 70..240){"Réglages non compatibles"}
  val volumes=prefs.getString("vol",null)?.split(',')?.map{it.toDouble()}?:error("Volumes absents")
  require(volumes.size==6 && volumes.all{it.isFinite() && it in 0.0..1.0}){"Volumes invalides"}
  val grid=JSONArray();for(l in 0..5){val row=JSONArray();for(s in 0 until steps)row.put(bits[l*64+s]=='1');grid.put(row)}
  val vols=JSONArray();volumes.forEach{vols.put(it)}
  val doc=JSONObject().put("format","moktek-portable-pattern-v1").put("steps",steps).put("bpm",bpm).put("grid",grid).put("volumes",vols).put("origin","android")
  val content=doc.toString().toByteArray(Charsets.UTF_8)
  val path="metadata/portable-pattern.json"
  val manifest=JSONObject().put("format","moktek-exchange").put("version",1).put("origin","android").put("hardwareWrite",false).put("files",JSONObject().put(path,sha(content)))
  return ByteArrayOutputStream().also{out->ZipOutputStream(out).use{zip->for((name,data) in listOf(path to content,"manifest.json" to manifest.toString().toByteArray(Charsets.UTF_8))){zip.putNextEntry(ZipEntry(name));zip.write(data);zip.closeEntry()}}}.toByteArray()
 }
}
