package org.moktek.kaoss

import kotlin.math.*
import java.nio.ByteBuffer
import java.nio.ByteOrder

internal object SoundLab {
 fun transform(pcm:ByteArray, channels:Int, a:Int, b:Int, mode:String, gain:Float=1f):ByteArray {
  require(channels in 1..2 && a>=0 && b>a && b<=pcm.size/(channels*2))
  val out=pcm.copyOf(); val buf=ByteBuffer.wrap(out).order(ByteOrder.LITTLE_ENDIAN)
  val sample=ByteBuffer.wrap(pcm).order(ByteOrder.LITTLE_ENDIAN)
  var peak=0
  if(mode=="NORMALISER") for(i in a*channels until b*channels) peak=maxOf(peak,abs(buf.getShort(i*2).toInt()))
  val n=b-a
  for(f in 0 until n) for(c in 0 until channels){
   val index=((a+f)*channels+c)*2
   val source=if(mode=="INVERSER") ((b-1-f)*channels+c)*2 else index
   val v=sample.getShort(source).toDouble()
   val g=when(mode){"NORMALISER"->if(peak==0)1.0 else 32700.0/peak;"GAIN"->gain.toDouble();"FONDU IN"->f.toDouble()/maxOf(1,n-1);"FONDU OUT"->(n-1-f).toDouble()/maxOf(1,n-1);else->1.0}
   buf.putShort(index,(v*g).roundToInt().coerceIn(-32768,32767).toShort())
  }
  return out
 }
 fun kick(rate:Int, bpm:Int, pitch:Float, decay:Float, drive:Float):ByteArray {
  val n=(rate*60.0/bpm).toInt();val buf=ByteBuffer.allocate(n*2).order(ByteOrder.LITTLE_ENDIAN);var phase=0.0
  for(i in 0 until n){val t=i.toDouble()/rate;phase+=2*PI*(pitch+140*exp(-t*45))/rate;val env=exp(-t/decay)*minOf(1.0,t*1000)*minOf(1.0,(n-i)/120.0);val v=tanh(sin(phase)*drive)*env;buf.putShort((v*30000).roundToInt().toShort())};return buf.array()
 }
 fun bpm(pcm:ByteArray,rate:Int,channels:Int):Int? {
  val frames=pcm.size/(channels*2); val hop=rate/100; if(frames<rate*4)return null
  val buf=ByteBuffer.wrap(pcm).order(ByteOrder.LITTLE_ENDIAN);val n=frames/hop;val flux=DoubleArray(n);var prev=0.0
  for(i in 0 until n){var e=0.0;repeat(hop*channels){e+=abs(buf.short.toInt())};e/=hop*channels;flux[i]=maxOf(0.0,e-prev);prev=e}
  val mean=flux.average();for(i in flux.indices)flux[i]-=mean
  var best=0.0;var lagBest=0
  for(lag in 25..86){var xy=0.0;var xx=0.0;var yy=0.0;for(i in lag until n){val x=flux[i];val y=flux[i-lag];xy+=x*y;xx+=x*x;yy+=y*y};val score=xy/sqrt(maxOf(1.0,xx*yy));if(score>best){best=score;lagBest=lag}}
  return if(best<0.18||lagBest==0)null else (6000.0/lagBest).roundToInt()
 }
}
