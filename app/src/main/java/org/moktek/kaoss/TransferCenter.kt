package org.moktek.kaoss

import android.content.Context
import android.hardware.usb.UsbManager
import android.media.midi.*
import android.os.Handler
import android.os.Looper
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.util.Locale

/** V17 : identité MIDI seulement ; aucune écriture de données Korg. */
private class IdentityMonitor(private val context:Context) {
 private val handler = Handler(Looper.getMainLooper())
 private val manager = context.getSystemService(Context.MIDI_SERVICE) as? MidiManager
 var state by mutableStateOf("DÉCONNECTÉ")
  private set
 var selected by mutableStateOf("Aucun")
  private set
 var foundIdentity by mutableStateOf("Aucune réponse d’identité reçue")
  private set
 var devices by mutableStateOf(emptyList<MidiDeviceInfo>())
  private set
 val events = mutableStateListOf<String>()
 private var opened: MidiDevice? = null
 private var readPort: MidiOutputPort? = null
 private var sendPort: MidiInputPort? = null
 private var epoch=0
 private var bytesReceived=0L
 private val framer = SysexFramer()
 private var receiver: MidiReceiver?=null
 fun refresh() {
  devices=manager?.devices?.toList() ?: emptyList()
  if(devices.isEmpty() && opened==null) state="AUCUN PÉRIPHÉRIQUE MIDI"
 }
 fun close() {
  epoch++
  runCatching { readPort?.close() }
  runCatching { sendPort?.close() }
  runCatching { opened?.close() }
  receiver=null; readPort=null; sendPort=null; opened=null
  framer.reset();selected="Aucun";state="DÉCONNECTÉ"
 }
 fun open(info:MidiDeviceInfo) {
  close()
  val request=epoch
  state="OUVERTURE…"
  manager?.openDevice(info,{ dev ->
   if(request!=epoch){runCatching{dev?.close()};return@openDevice}
   if(dev==null){state="ÉCHEC DE CONNEXION";return@openDevice}
   val readNumber=info.ports.firstOrNull {it.type==MidiDeviceInfo.PortInfo.TYPE_OUTPUT}?.portNumber
   val sendNumber=info.ports.firstOrNull {it.type==MidiDeviceInfo.PortInfo.TYPE_INPUT}?.portNumber
   val read=readNumber?.let{runCatching{dev.openOutputPort(it)}.getOrNull()}
   val send=sendNumber?.let{runCatching{dev.openInputPort(it)}.getOrNull()}
   if(read==null && send==null){runCatching{dev.close()};state="PORTS INACCESSIBLES";return@openDevice}
   opened=dev;readPort=read;sendPort=send
   framer.reset()
   val incoming=object:MidiReceiver(){
    override fun onSend(msg:ByteArray,offset:Int,count:Int,timestamp:Long){
     if(count<=0||request!=epoch)return
     // Traitement séquentiel sur le thread principal, sans conserver de buffer système mutable.
     val copy=msg.copyOfRange(offset,offset+count)
     handler.post {
      if(request!=epoch)return@post
      bytesReceived+=copy.size
      val hex=copy.take(64).joinToString(" "){String.format(Locale.US,"%02X",it.toInt() and 255)}
      events.add(0,"RX ${copy.size} octets : $hex${if(copy.size>64)" …" else ""}")
      for(frame in framer.accept(copy,0,copy.size)) {
       val identity=identifyMidiReply(frame)
       if(identity!=null){
        foundIdentity="${identity.manufacturer} | canal ID ${identity.deviceId} | famille ${identity.family} | modèle ${identity.model} | firmware ${identity.version}"
        events.add(0,"IDENTITÉ : $foundIdentity")
       }else if(frame.size>2 && (frame[1].toInt() and 255)==0x42){
        events.add(0,"SysEx Korg reçu (${frame.size} octets) : non interprété et non sauvegardé")
       }
      }
      while(events.size>80)events.removeAt(events.lastIndex)
     }
    }
   }
   receiver=incoming
   runCatching{read?.connect(incoming)}
   selected=info.properties.getString(MidiDeviceInfo.PROPERTY_NAME) ?: "Appareil MIDI #${info.id}"
   state=when {
    read!=null && send!=null -> "CONNECTÉ • RX + TX identité"
    read!=null -> "ÉCOUTE SEULE • pas de port d'envoi"
    else -> "ENVOI SEUL • aucune réception possible"
   }
  },handler)
 }
 fun requestIdentity() {
  val port=sendPort
  if(port==null){events.add(0,"Aucun port MIDI IN : demande impossible");return}
  // Universal Non Real-Time Identity Request. Ne modifie pas mémoire, programmes ou samples.
  val inquiry=byteArrayOf(0xF0.toByte(),0x7E,0x7F,0x06,0x01,0xF7.toByte())
  runCatching{port.send(inquiry,0,inquiry.size)}
   .onSuccess{events.add(0,"TX F0 7E 7F 06 01 F7 (demande d’identité seule)")}
   .onFailure{state="ERREUR D’ENVOI : ${it.message}"}
 }
 fun clear(){events.clear();bytesReceived=0;foundIdentity="Aucune réponse d’identité reçue"}
 fun usbDescription():String {
  val usb=context.getSystemService(Context.USB_SERVICE) as? UsbManager
  return usb?.deviceList?.values?.joinToString("\n"){"VID %04X • PID %04X".format(Locale.US,it.vendorId,it.productId)}?.ifBlank{"Aucun périphérique USB visible"}?:"USB non disponible"
 }
 fun report(declaredModel:String)=buildString {
  appendLine("mokteK KAOSS STUDIO — V17 / IDENTITÉ MIDI")
  appendLine("Modèle choisi par l’utilisateur : $declaredModel (non confirmé par cette sélection)")
  appendLine("État : $state ; périphérique ouvert : $selected")
  appendLine("Réponse : $foundIdentity")
  appendLine("USB : ${usbDescription()}")
  appendLine("Périphériques MIDI Android : ${devices.size}")
  appendLine("Octets reçus : $bytesReceived")
  appendLine("Aucune écriture dans la mémoire du KP3/KP3+ ; seule la demande d’identité peut être émise.")
  appendLine("Journal borné à 80 entrées, affichage tronqué à 64 octets par paquet.")
  appendLine()
  events.forEach{appendLine(it)}
 }
}

@Composable
internal fun TransferCenter(model:String) {
 val context=androidx.compose.ui.platform.LocalContext.current
 val monitor=remember {IdentityMonitor(context.applicationContext)}
 val red=Color(0xffff493e);val bone=Color(0xffe9dac2)
 val card=Color(0xff211d1a);val steel=Color(0xff887766)
 var message by remember{mutableStateOf("")}
 val export=rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("text/plain")){uri->
  if(uri!=null)runCatching {context.contentResolver.openOutputStream(uri)?.use{it.write(monitor.report(model).toByteArray(Charsets.UTF_8))}?:error("Fichier inaccessible")}
   .onSuccess{message="Rapport enregistré"}.onFailure{message="Export impossible : ${it.message}"}
 }
 DisposableEffect(monitor){monitor.refresh();onDispose{monitor.close()}}
 Column(Modifier.fillMaxWidth(),verticalArrangement=Arrangement.spacedBy(10.dp)) {
  Text("TRANSFER CENTER • V17",fontSize=20.sp,color=red)
  Text("IDENTIFICATION MIDI SANS ÉCRITURE",fontSize=12.sp,color=bone)
  Text("La demande d’identité standard ne modifie ni les réglages ni les samples. Les transferts Korg restent désactivés.",fontSize=11.sp,color=bone)
  Column(Modifier.fillMaxWidth().background(card,RoundedCornerShape(8.dp)).border(1.dp,steel,RoundedCornerShape(8.dp)).padding(10.dp),verticalArrangement=Arrangement.spacedBy(7.dp)) {
   Text("PROFIL CHOISI : $model",fontSize=12.sp,color=red)
   Text(monitor.state,fontSize=12.sp,color=bone)
   Text("PORT : ${monitor.selected}",fontSize=11.sp,color=bone)
   Text(monitor.foundIdentity,fontSize=11.sp,color=bone)
   Text("USB : ${monitor.usbDescription()}",fontSize=10.sp,color=bone)
   Row(horizontalArrangement=Arrangement.spacedBy(8.dp)) {
    OutlinedButton(onClick={monitor.refresh()},modifier=Modifier.weight(1f)){Text("ACTUALISER",fontSize=10.sp)}
    OutlinedButton(onClick={monitor.close()},modifier=Modifier.weight(1f)){Text("DÉCONNECTER",fontSize=10.sp)}
   }
  }
  Column(Modifier.fillMaxWidth().background(card,RoundedCornerShape(8.dp)).border(1.dp,steel,RoundedCornerShape(8.dp)).padding(10.dp),verticalArrangement=Arrangement.spacedBy(6.dp)) {
   Text("CHOISIR UNE INTERFACE MIDI",fontSize=12.sp,color=red)
   if(monitor.devices.isEmpty()) Text("Aucune interface trouvée. Vérifier USB OTG ou interface USB-MIDI DIN.",fontSize=11.sp,color=bone)
   monitor.devices.forEach{dev->
    val name=dev.properties.getString(MidiDeviceInfo.PROPERTY_NAME)?:"MIDI #${dev.id}"
    val canRead=dev.ports.any{it.type==MidiDeviceInfo.PortInfo.TYPE_OUTPUT}
    val canWrite=dev.ports.any{it.type==MidiDeviceInfo.PortInfo.TYPE_INPUT}
    OutlinedButton(onClick={monitor.open(dev)},modifier=Modifier.fillMaxWidth()){
     Text("$name • ${if(canRead)"RX" else "—"} / ${if(canWrite)"TX" else "—"}",fontSize=10.sp)
    }
   }
   Button(onClick={monitor.requestIdentity()},enabled=monitor.state.startsWith("CONNECTÉ")||monitor.state.startsWith("ENVOI"),modifier=Modifier.fillMaxWidth()){
    Text("DEMANDER L’IDENTITÉ MIDI",fontSize=11.sp)
   }
   Text("Une interface DIN peut apparaître sous son propre nom : la réponse SysEx sert à identifier l’instrument derrière elle.",fontSize=10.sp,color=bone)
  }
  Column(Modifier.fillMaxWidth().background(card,RoundedCornerShape(8.dp)).border(1.dp,steel,RoundedCornerShape(8.dp)).padding(10.dp),verticalArrangement=Arrangement.spacedBy(6.dp)){
   Text("JOURNAL DE DIAGNOSTIC",fontSize=12.sp,color=red)
   Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){
    OutlinedButton(onClick={monitor.clear()},modifier=Modifier.weight(1f)){Text("EFFACER",fontSize=10.sp)}
    OutlinedButton(onClick={export.launch("moktek_identite_v17.txt")},modifier=Modifier.weight(1f)){Text("EXPORTER",fontSize=10.sp)}
   }
   if(monitor.events.isEmpty())Text("Aucun message reçu.",fontSize=11.sp,color=bone)
   monitor.events.take(14).forEach{Text(it,fontSize=10.sp,fontFamily=FontFamily.Monospace,color=bone)}
  }
  if(message.isNotBlank())Text(message,fontSize=12.sp,color=red)
 }
}
