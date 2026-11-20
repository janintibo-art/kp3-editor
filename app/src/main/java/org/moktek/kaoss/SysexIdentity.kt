package org.moktek.kaoss

/** Reconstitue uniquement les trames SysEx bornées, sans émission vers le matériel. */
internal class SysexFramer(private val limit: Int = 4096) {
 private val buffer = ArrayList<Byte>()
 fun accept(bytes: ByteArray, offset: Int, count: Int): List<ByteArray> {
  val frames = mutableListOf<ByteArray>()
  if (offset < 0 || count < 0 || offset > bytes.size - count) return frames
  for (i in offset until offset + count) {
   val value = bytes[i].toInt() and 0xff
   if (value == 0xF0) { buffer.clear(); buffer.add(bytes[i]); continue }
   if (buffer.isEmpty()) continue
   // Les messages temps réel MIDI peuvent être intercalés sans faire partie du SysEx.
   if (value >= 0xF8) continue
   if (value in 0x80..0xF6) { buffer.clear(); continue }
   if (buffer.size >= limit) { buffer.clear(); continue }
   buffer.add(bytes[i])
   if (value == 0xF7) { frames.add(buffer.toByteArray()); buffer.clear() }
  }
  return frames
 }
 fun reset() = buffer.clear()
}

internal data class IdentityReply(val manufacturer: String, val deviceId: Int, val family: String, val model: String, val version: String)
internal fun identifyMidiReply(bytes: ByteArray): IdentityReply? {
 if (bytes.size < 15 || (bytes[0].toInt() and 255) != 0xF0 || (bytes.last().toInt() and 255) != 0xF7) return null
 if ((bytes[1].toInt() and 255) != 0x7E || (bytes[3].toInt() and 255) != 0x06 || (bytes[4].toInt() and 255) != 0x02) return null
 val maker = bytes[5].toInt() and 255
 val manu = if(maker == 0x42) "Korg" else "Autre fabricant (0x%02X)".format(maker)
 // Réponse universelle : F0 7E device 06 02 manufacturer family(2) model(2) version(4) F7
 if (maker == 0) return null // Cas fabricant à 3 octets non interprété dans cette version.
 if (bytes.size != 15) return null
 fun part(start: Int, n: Int): String = (start until start+n).joinToString(" ") { "%02X".format(bytes[it].toInt() and 255) }
 return IdentityReply(manu, bytes[2].toInt() and 255, part(6,2), part(8,2), part(10,4))
}
