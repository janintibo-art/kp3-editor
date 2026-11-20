package org.moktek.kaoss

import android.content.SharedPreferences
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.json.JSONObject

/** Local transmitter profile. This does not rewrite KP3/KP3+ hardware globals. */
data class MidiLocalProfile(
 val channel: Int = 1,
 val x: Int = 12,
 val y: Int = 13,
 val touch: Int = 92,
 val depth: Int = 94,
 val level: Int = 93,
 val hold: Int = 95,
 val ccEnabled: Boolean = true,
 val programEnabled: Boolean = true,
 val noteEnabled: Boolean = true,
 val clockEnabled: Boolean = false
) {
 fun mapController(factoryNumber:Int):Int = when(factoryNumber){
  12 -> x; 13 -> y; 92 -> touch; 94 -> depth; 93 -> level; 95 -> hold; else -> factoryNumber
 }
 fun saveJson():String = JSONObject().put("channel",channel).put("x",x).put("y",y)
  .put("touch",touch).put("depth",depth).put("level",level).put("hold",hold)
  .put("cc",ccEnabled).put("program",programEnabled).put("note",noteEnabled)
  .put("clock",clockEnabled).toString()
 companion object {
  fun fromJson(raw:String?):MidiLocalProfile = runCatching {
   if(raw.isNullOrBlank()) return MidiLocalProfile()
   val j=JSONObject(raw)
   MidiLocalProfile(
    channel=j.optInt("channel",1).coerceIn(1,16),
    x=j.optInt("x",12).coerceIn(0,127), y=j.optInt("y",13).coerceIn(0,127),
    touch=j.optInt("touch",92).coerceIn(0,127),
    depth=j.optInt("depth",94).coerceIn(0,127),
    level=j.optInt("level",93).coerceIn(0,127),
    hold=j.optInt("hold",95).coerceIn(0,127),
    ccEnabled=j.optBoolean("cc",true), programEnabled=j.optBoolean("program",true),
    noteEnabled=j.optBoolean("note",true), clockEnabled=j.optBoolean("clock",false)
   )
  }.getOrDefault(MidiLocalProfile())
 }
}

internal fun loadMidiLocalProfile(prefs:SharedPreferences,model:String):MidiLocalProfile =
 MidiLocalProfile.fromJson(prefs.getString("midi_profile_$model",null))

@Composable
internal fun MidiGlobalEditor(
 model:String,
 profile:MidiLocalProfile,
 onChange:(MidiLocalProfile)->Unit,
 onReset:()->Unit
){
 val red=Color(0xffff493e)
 val bone=Color(0xffe9dac2)
 val panel=Color(0xff211d1a)
 Column(verticalArrangement=Arrangement.spacedBy(10.dp)){
  Text("MIDI & GLOBAL — $model",color=red,fontSize=20.sp)
  Text("PROFIL LOCAL — Les réglages de cette page changent les messages envoyés par l'application, pas les paramètres enregistrés dans le Kaoss Pad.",color=bone,fontSize=12.sp)
  Column(Modifier.fillMaxWidth().background(panel,RoundedCornerShape(7.dp)).border(1.dp,Color(0xff887766),RoundedCornerShape(7.dp)).padding(12.dp),verticalArrangement=Arrangement.spacedBy(6.dp)){
   Text("CANAL D'ÉMISSION MIDI : ${profile.channel}",color=bone)
   Slider(value=profile.channel.toFloat(),onValueChange={onChange(profile.copy(channel=it.toInt().coerceIn(1,16)))},valueRange=1f..16f,steps=14)
   Text("Affectations de commandes (CC 0–127)",color=red)
   listOf(Triple("PAD X",profile.x,"x"),Triple("PAD Y",profile.y,"y"),Triple("PAD TOUCH",profile.touch,"touch"),Triple("FX DEPTH",profile.depth,"depth"),Triple("LEVEL / CC93",profile.level,"level"),Triple("HOLD",profile.hold,"hold")).forEach{(label,number,id)->
    Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){
     Text(label,color=bone,fontSize=12.sp,modifier=Modifier.weight(1f))
     Text("CC $number",color=red,fontSize=12.sp,modifier=Modifier.width(60.dp))
     IconButton(onClick={onChange(when(id){"x"->profile.copy(x=(number-1).coerceAtLeast(0));"y"->profile.copy(y=(number-1).coerceAtLeast(0));"touch"->profile.copy(touch=(number-1).coerceAtLeast(0));"depth"->profile.copy(depth=(number-1).coerceAtLeast(0));"level"->profile.copy(level=(number-1).coerceAtLeast(0));else->profile.copy(hold=(number-1).coerceAtLeast(0))})}){Text("−",color=bone)}
     IconButton(onClick={onChange(when(id){"x"->profile.copy(x=(number+1).coerceAtMost(127));"y"->profile.copy(y=(number+1).coerceAtMost(127));"touch"->profile.copy(touch=(number+1).coerceAtMost(127));"depth"->profile.copy(depth=(number+1).coerceAtMost(127));"level"->profile.copy(level=(number+1).coerceAtMost(127));else->profile.copy(hold=(number+1).coerceAtMost(127))})}){Text("+",color=bone)}
    }
   }
   Text("FILTRES D'ÉMISSION DE L'APPLICATION",color=red)
   MidiFilterLine("Messages Control Change",profile.ccEnabled){onChange(profile.copy(ccEnabled=it))}
   MidiFilterLine("Program Change",profile.programEnabled){onChange(profile.copy(programEnabled=it))}
   MidiFilterLine("Notes MIDI (banques A–D)",profile.noteEnabled){onChange(profile.copy(noteEnabled=it))}
   MidiFilterLine("Horloge MIDI — non émise en V13",profile.clockEnabled){onChange(profile.copy(clockEnabled=it))}
   Text("Le filtre d'horloge est mémorisé pour une prochaine version. Aucune horloge MIDI n'est générée en V13.",color=bone,fontSize=11.sp)
   OutlinedButton(onClick=onReset,modifier=Modifier.fillMaxWidth()){Text("RÉTABLIR LES VALEURS D'USINE LOCALES")}
  }
  Text("Pour modifier les paramètres globaux internes du KP3/KP3+, utiliser encore les menus de la machine. La lecture/écriture SysEx sera ajoutée après validation du protocole.",color=bone,fontSize=12.sp)
 }
}

@Composable
private fun MidiFilterLine(label:String,checked:Boolean,action:(Boolean)->Unit){
 Row(verticalAlignment=Alignment.CenterVertically){
  Text(label,color=Color(0xffe9dac2),modifier=Modifier.weight(1f),fontSize=12.sp)
  Switch(checked=checked,onCheckedChange=action)
 }
}
