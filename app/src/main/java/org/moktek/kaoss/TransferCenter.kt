package org.moktek.kaoss

import android.content.Context
import android.hardware.usb.UsbManager
import android.media.midi.MidiDevice
import android.media.midi.MidiDeviceInfo
import android.media.midi.MidiManager
import android.media.midi.MidiOutputPort
import android.media.midi.MidiReceiver
import android.os.Handler
import android.os.Looper
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.util.Locale

/** Lecture MIDI exclusivement. Aucune commande de transfert, aucun SysEx sortant. */
private class IncomingMidiMonitor(private val context:Context) {
 private val handler=Handler(Looper.getMainLooper())
 private val manager=context.getSystemService(Context.MIDI_SERVICE) as? MidiManager
 var state by mutableStateOf("DÉCONNECTÉ")
  private set
 var selected by mutableStateOf("")
  private set
 var ports by mutableStateOf(emptyList<Pair<MidiDeviceInfo,Int>>())
  private set
 val events=mutableStateListOf<String>()
 private var opened:MidiDevice?=null
 private var output:MidiOutputPort?=null
 private var epoch=0
 private var byteCount=0L
 private var packetCount=0L
 fun refresh(){
  val found=manager?.devices?.flatMap{dev->dev.ports.filter{it.type==MidiDeviceInfo.PortInfo.TYPE_OUTPUT}.map{Pair(dev,it.portNumber)}} ?: emptyList()
  ports=found
  if(found.isEmpty())state="AUCUN PORT MIDI SORTANT DÉTECTÉ"
 }
 fun close(){
  epoch++
  runCatching { output?.close() }; runCatching {opened?.close()}
  output=null;opened=null;state="DÉCONNECTÉ";selected=""
 }
 fun listen(info:MidiDeviceInfo, number:Int){
  close()
  val request=epoch
  state="OUVERTURE DU PORT…"
  manager?.openDevice(info,{device->
   if(request!=epoch){runCatching{device?.close()};return@openDevice}
   if(device==null){state="OUVERTURE REFUSÉE";return@openDevice}
   val receiver=object:MidiReceiver(){
    override fun onSend(data:ByteArray, offset:Int, count:Int, timestamp:Long){
     if(request!=epoch||count<=0)return
     val n=count.coerceAtMost(64)
     val txt=(offset until offset+n).joinToString(" "){"%02X".format(Locale.US,data[it].toInt() and 0xff)}
     handler.post {
      if(request!=epoch)return@post
      packetCount++;byteCount+=count
      val type=if((data[offset].toInt() and 0xff)==0xf0)"SysEx (début)" else "MIDI"
      events.add(0,"$type  ${count} octets : $txt${if(count>n)" …" else ""}")
      if(events.size>75)events.removeAt(events.lastIndex)
     }
    }
   }
   val p=runCatching {device.openOutputPort(number)}.getOrNull()
   if(p==null){runCatching{device.close()};state="PORT INACCESSIBLE";return@openDevice}
   opened=device;output=p;p.connect(receiver)
   selected="${info.properties.getString(MidiDeviceInfo.PROPERTY_NAME) ?: "Périphérique MIDI"} / OUT $number"
   state="ÉCOUTE ACTIVE (LECTURE SEULE)"
  },handler)
 }
 fun usbDescription():String{
  val usb=context.getSystemService(Context.USB_SERVICE) as? UsbManager
  return usb?.deviceList?.values?.joinToString("\n"){"VID %04X • PID %04X".format(Locale.US,it.vendorId,it.productId)}?.ifBlank{"Aucun appareil USB détecté"} ?: "USB indisponible"
 }
 fun exportReport(model:String):String=buildString {
  appendLine("mokteK KAOSS STUDIO V15 — DIAGNOSTIC TRANSFER CENTER")
  appendLine("Modèle déclaré : $model (non identifié automatiquement)")
  appendLine("État : $state")
  appendLine("Port : $selected")
  appendLine("USB : ${usbDescription()}")
  appendLine("Paquets : $packetCount ; octets : $byteCount")
  appendLine("Journal limité aux 75 derniers fragments, 64 octets maximum par fragment.")
  appendLine("Aucun transfert vers la mémoire matérielle n'a été exécuté.")
  appendLine()
  events.forEach{appendLine(it)}
 }
 fun clear(){events.clear();packetCount=0;byteCount=0}
}

@Composable
internal fun TransferCenter(model:String){
 val context=androidx.compose.ui.platform.LocalContext.current
 val monitor=remember { IncomingMidiMonitor(context.applicationContext) }
 val red=Color(0xffff493e);val bone=Color(0xffe9dac2)
 val card=Color(0xff211d1a);val steel=Color(0xff887766)
 var msg by remember {mutableStateOf("")}
 val exporter=rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("text/plain")){uri->
  if(uri!=null) runCatching {context.contentResolver.openOutputStream(uri)?.use{it.write(monitor.exportReport(model).toByteArray(Charsets.UTF_8))} ?: error("Fichier inaccessible")}.onSuccess{msg="Diagnostic enregistré"}.onFailure{msg="Export impossible : ${it.message}"}
 }
 DisposableEffect(monitor){monitor.refresh();onDispose{monitor.close()}}
 Column(Modifier.fillMaxWidth(),verticalArrangement=Arrangement.spacedBy(9.dp)){
  Text("TRANSFER CENTER • V15",fontSize=21.sp,color=red)
  Text("Diagnostic de connexion en lecture seule pour KP3 / KP3+. Les commandes d'écriture et le transfert des samples ne sont PAS actifs.",fontSize=12.sp,color=bone)
  Column(Modifier.fillMaxWidth().background(card,RoundedCornerShape(8.dp)).border(1.dp,steel,RoundedCornerShape(8.dp)).padding(12.dp),verticalArrangement=Arrangement.spacedBy(7.dp)) {
   Text("APPAREIL DÉCLARÉ : $model",fontSize=13.sp,color=red)
   Text("ÉTAT : ${monitor.state}",fontSize=13.sp,color=bone)
   Text("USB : ${monitor.usbDescription()}",fontSize=12.sp,color=bone)
   Text("Port : ${monitor.selected.ifEmpty {"aucun"}}",fontSize=12.sp,color=bone)
   Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){
    OutlinedButton(onClick={monitor.refresh()},modifier=Modifier.weight(1f)){Text("ACTUALISER",fontSize=11.sp)}
    OutlinedButton(onClick={monitor.close()},modifier=Modifier.weight(1f)){Text("ARRÊTER",fontSize=11.sp)}
   }
  }
  Column(Modifier.fillMaxWidth().background(card,RoundedCornerShape(8.dp)).border(1.dp,steel,RoundedCornerShape(8.dp)).padding(12.dp),verticalArrangement=Arrangement.spacedBy(5.dp)){
   Text("PORTS POUR RECEVOIR DES DONNÉES",color=red,fontSize=13.sp)
   Text("Un port « OUT » de la machine peut être lu par le téléphone. Le port MIDI utilisé dans Live pour envoyer des notes est différent.",color=bone,fontSize=11.sp)
   if(monitor.ports.isEmpty())Text("Aucun port disponible. Essayer l’OTG ou une interface USB-MIDI compatible Android.",color=bone,fontSize=12.sp)
   monitor.ports.forEach { (info,number)->
    val name=info.properties.getString(MidiDeviceInfo.PROPERTY_NAME) ?: "Périphérique MIDI"
    OutlinedButton(onClick={monitor.listen(info,number)},modifier=Modifier.fillMaxWidth()) { Text("ÉCOUTER : $name / OUT $number",fontSize=11.sp) }
   }
  }
  Column(Modifier.fillMaxWidth().background(card,RoundedCornerShape(8.dp)).border(1.dp,steel,RoundedCornerShape(8.dp)).padding(12.dp),verticalArrangement=Arrangement.spacedBy(7.dp)){
   Text("JOURNAL MIDI ENTRANT",color=red,fontSize=13.sp)
   Text("Messages reçus : ${monitor.events.size} affichés ; aucun message n'est envoyé par cet écran.",color=bone,fontSize=11.sp)
   Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){
    OutlinedButton(onClick={monitor.clear()},modifier=Modifier.weight(1f)){Text("EFFACER",fontSize=11.sp)}
    OutlinedButton(onClick={exporter.launch("moktek_transfer_v15.txt")},modifier=Modifier.weight(1f)){Text("EXPORTER",fontSize=11.sp)}
   }
   if(monitor.events.isEmpty())Text("Aucun message reçu pour le moment.",color=bone,fontSize=11.sp)
   monitor.events.take(15).forEach { Text(it,fontFamily=FontFamily.Monospace,fontSize=10.sp,color=bone) }
  }
  Text("Étape suivante : décoder et valider les réponses SysEx propres à chaque modèle avant d'autoriser les sauvegardes et transferts matériels. Ne pas confondre écoute MIDI et sauvegarde du KP3.",color=bone,fontSize=11.sp)
  if(msg.isNotBlank())Text(msg,color=red,fontSize=12.sp)
 }
}
