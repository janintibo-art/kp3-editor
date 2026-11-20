package org.moktek.kaoss

import kotlin.math.*
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.Random

internal data class SynthPreset(val name:String,val kind:String,val bpm:Int,val pitch:Float,val decay:Float,val drive:Float,val tone:Float)
internal object SynthFactory {
 val presets=listOf(
  SynthPreset("Hardtek kick","Kick",180,48f,.19f,6f,.7f),
  SynthPreset("Tribe kick","Kick",165,58f,.14f,2.5f,.4f),
  SynthPreset("Acid spiral","Acid",174,55f,.18f,3f,.72f),
  SynthPreset("Dark bass","Bass",170,46f,.25f,2f,.35f),
  SynthPreset("Tek snare","Snare",180,170f,.10f,2f,.65f),
  SynthPreset("Metal hat","Hat",180,80f,.045f,1.5f,.85f),
  SynthPreset("Tribe tom","Tom",165,110f,.16f,2f,.5f))
 fun render(rate:Int,bpm:Int,kind:String,pitch:Float,decay:Float,drive:Float,tone:Float):ByteArray {
  require(rate in 8000..48000 && bpm in 70..240 && pitch in 25f..400f && decay in .02f.. .5f && drive in 1f..8f && tone in 0f..1f)
  val n=(rate*60.0/bpm).roundToInt();val out=ByteBuffer.allocate(n*2).order(ByteOrder.LITTLE_ENDIAN)
  val random=Random(413);var phase=0.0;var low=0.0;var band=0.0;var prevNoise=0.0
  val d=decay.toDouble();val p=pitch.toDouble();val color=tone.toDouble()
  for(i in 0 until n){
   val t=i.toDouble()/rate;val noise=random.nextDouble()*2-1;val high=noise-prevNoise;prevNoise=noise
   val freq=when(kind){"Kick"->p+(80+180*color)*exp(-t*45);"Tom"->p+80*exp(-t*35);"Snare"->p+60*exp(-t*60);else->p}
   phase=(phase+freq/rate)%1.0;val sine=sin(2*PI*phase);val saw=2*phase-1
   val raw=when(kind){
    "Acid"->{val cutoff=180+color*3600*exp(-t/(d*.65));val g=tan(PI*cutoff.coerceAtMost(rate*.2)/rate);val k=.35+(1-color)*1.2;val a=1/(1+g*(g+k));val v1=a*(band+g*(saw-low));val v2=low+g*v1;band=2*v1-band;low=2*v2-low;v2+.35*v1}
    "Bass"-> .8*sine+.2*sin(4*PI*phase)
    "Snare"-> .35*sine*exp(-t*25)+.65*high
    "Hat"-> high*.65+sin(2*PI*phase*37)*.15
    "Tom"-> sine+.15*sin(4*PI*phase)
    else->sine+color*.22*sin(6*PI*phase)
   }
   val env=exp(-t/d)*minOf(1.0,t*1500)*minOf(1.0,(n-1-i)/120.0)
   val v=tanh(raw*drive)*env*.92
   out.putShort((v*32767).roundToInt().coerceIn(-32768,32767).toShort())
  };return out.array()
 }
}
