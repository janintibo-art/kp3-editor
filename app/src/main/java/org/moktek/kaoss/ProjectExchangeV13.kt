package org.moktek.kaoss

import android.content.Context
import org.json.JSONObject
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.security.MessageDigest
import java.util.UUID
import java.util.zip.ZipInputStream

/** Import des WAV Windows V13 comme fichiers de référence locaux, JAMAIS sur le matériel Korg. */
internal object ProjectExchangeV13 {
    private const val MAX_TOTAL = 192L * 1024 * 1024
    private const val MAX_SINGLE = 48L * 1024 * 1024
    private val audioPath = Regex("audio/[ABCD][0-7]\\.wav")
    private val metadataPath = Regex("metadata/[a-zA-Z0-9._-]+\\.json")
    private fun hash(data: ByteArray): String = MessageDigest.getInstance("SHA-256")
        .digest(data).joinToString("") { "%02x".format(it.toInt() and 255) }
    fun importArchive(context:Context, data:ByteArray):String {
        require(data.size.toLong()<=MAX_TOTAL){"Archive trop volumineuse"}
        val entries=linkedMapOf<String,ByteArray>()
        var total=0L
        ZipInputStream(ByteArrayInputStream(data)).use { zip->
            while(true){
                val entry=zip.nextEntry ?: break
                val name=entry.name
                require(!entry.isDirectory && (name=="manifest.json" ||
                    audioPath.matches(name) || metadataPath.matches(name))){"Fichier d'échange non autorisé : $name"}
                require(!entries.containsKey(name) && entries.size<70){"Archive dupliquée ou trop grande"}
                val buffer=ByteArrayOutputStream();val chunk=ByteArray(8192)
                while(true){val n=zip.read(chunk);if(n<0)break;require(buffer.size().toLong()+n<=MAX_SINGLE){"Entrée trop volumineuse"};buffer.write(chunk,0,n)}
                total+=buffer.size().toLong();require(total<=MAX_TOTAL){"Taille totale dépassée"}
                entries[name]=buffer.toByteArray();zip.closeEntry()
            }
        }
        val manifest=JSONObject(String(entries["manifest.json"]?:error("Manifest manquant"),Charsets.UTF_8))
        require(manifest.optString("format")=="moktek-exchange" && manifest.optInt("version")==1){"Format incompatible"}
        val files=manifest.getJSONObject("files")
        require(files.length()==entries.size-1){"Fichiers manquants ou ajoutés"}
        entries.forEach { (name,bytes)->if(name!="manifest.json")require(files.optString(name)==hash(bytes)){
            "Intégrité SHA-256 non conforme : $name"} }
        // Basic RIFF/PCM validation. WAV decoding and assignment to actual bank slots are separate operations.
        val wavs=entries.filterKeys{audioPath.matches(it)}
        wavs.forEach { (_,bytes)->
            require(bytes.size>=44 && String(bytes,0,4,Charsets.US_ASCII)=="RIFF" &&
                String(bytes,8,4,Charsets.US_ASCII)=="WAVE" &&
                String(bytes,12,4,Charsets.US_ASCII)=="fmt " &&
                (bytes[20].toInt() and 255)==1 && bytes[21].toInt()==0 &&
                (bytes[22].toInt() and 255) in 1..2 && bytes[23].toInt()==0 &&
                (bytes[34].toInt() and 255)==16 && bytes[35].toInt()==0) {"WAV PCM 16 bits requis"}
        }
        val references=File(context.filesDir,"korg_reference_v14").apply{mkdirs()}
        val incoming=File(context.filesDir,"exchange_inbox_v13").apply{mkdirs()}
        val written=mutableListOf<File>()
        try {
            wavs.forEach { (name,bytes)->
                val source=name.substringAfter('/').removeSuffix(".wav")
                val dest=File(references,"v13_${source}_${UUID.randomUUID().toString().replace("-","").take(12)}.wav")
                require(dest.createNewFile()){ "Impossible de créer le fichier" }
                written.add(dest);dest.writeBytes(bytes)
            }
            entries.filterKeys{metadataPath.matches(it)}.forEach{ (name,bytes)->
                val dest=File(incoming,"${UUID.randomUUID().toString().take(8)}_${name.substringAfter('/')}")
                require(dest.createNewFile()){ "Impossible de créer les métadonnées" }
                written.add(dest);dest.writeBytes(bytes)
            }
        } catch(e:Exception){written.forEach{it.delete()};throw e}
        return "${wavs.size} WAV importés comme références locales (sans remplacer les banques). Métadonnées conservées : ${entries.keys.count{metadataPath.matches(it)}}. Aucun envoi au KP3."
    }
}
