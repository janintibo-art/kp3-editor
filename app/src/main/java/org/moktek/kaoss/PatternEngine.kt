package org.moktek.kaoss
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.roundToInt
internal object PatternEngine {
 val names=listOf("KICK","ACID","BASS","SNARE","HAT","TOM")
 fun render(bpm:Int,steps:Int,grid:List<Boolean>,volumes:List<Float>):ByteArray {
  require(bpm in 70..240 && steps in listOf(16,32,64) && grid.size==6*64 && volumes.size==6)
  val rate=44100; val interval=rate*60.0/bpm/4; val length=(steps*interval).roundToInt(); val mix=FloatArray(length)
  val presets=listOf(0,2,3,4,5,6).map{SynthFactory.presets[it]}
  for(lane in 0..5){ val p=presets[lane]; val raw=ByteBuffer.wrap(SynthFactory.render(rate,bpm,p.kind,p.pitch,p.decay,p.drive,p.tone)).order(ByteOrder.LITTLE_ENDIAN); val sound=FloatArray(raw.remaining()/2){raw.short/32768f}; for(step in 0 until steps){if(!grid[lane*64+step])continue;val offset=(step*interval).roundToInt();for(i in sound.indices)mix[(offset+i)%length]+=sound[i]*volumes[lane]*.32f} }
  return ByteBuffer.allocate(length*2).order(ByteOrder.LITTLE_ENDIAN).apply{mix.forEach{putShort((it.coerceIn(-1f,1f)*32767).roundToInt().toShort())}}.array()
 }
 fun wav(pcm:ByteArray)=ByteBuffer.allocate(44+pcm.size).order(ByteOrder.LITTLE_ENDIAN).apply{put("RIFF".toByteArray());putInt(36+pcm.size);put("WAVEfmt ".toByteArray());putInt(16);putShort(1);putShort(1);putInt(44100);putInt(88200);putShort(2);putShort(16);put("data".toByteArray());putInt(pcm.size);put(pcm)}.array()
}
