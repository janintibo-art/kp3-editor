package org.moktek.kaoss
import android.app.Activity
import android.graphics.Bitmap
import android.graphics.Canvas
import android.os.Build
import android.hardware.usb.UsbManager
import android.media.midi.MidiManager
import android.content.Context
import java.io.ByteArrayOutputStream
import java.util.zip.ZipOutputStream
import java.util.zip.ZipEntry
internal object TestReport {
 fun capture(activity:Activity,screen:String,status:String):ByteArray {
  val view=activity.window.decorView;require(view.width>0&&view.height>0){"Écran indisponible"}
  val bitmap=Bitmap.createBitmap(view.width,view.height,Bitmap.Config.ARGB_8888)
  val png=ByteArrayOutputStream();try{view.draw(Canvas(bitmap));check(bitmap.compress(Bitmap.CompressFormat.PNG,100,png))}finally{bitmap.recycle()}
  val config=activity.resources.configuration;val dm=activity.resources.displayMetrics
  val usb=activity.getSystemService(Context.USB_SERVICE) as? UsbManager;val midi=activity.getSystemService(Context.MIDI_SERVICE) as? MidiManager
  val report="mokteK Kaoss Studio V9\nÉcran : $screen\nAndroid : ${Build.VERSION.SDK_INT}\nRésolution capture : ${view.width} x ${view.height}\nZone dp : ${config.screenWidthDp} x ${config.screenHeightDp}\nDensité : ${dm.densityDpi}\nPolice : ${config.fontScale}\nMIDI : $status\nPériphériques MIDI : ${midi?.devices?.size ?: 0}\nUSB VID:PID : ${usb?.deviceList?.values?.joinToString { "%04X:%04X".format(it.vendorId,it.productId) } ?: "aucun"}\nCapture de la zone visible uniquement. Aucun test physique audio/MIDI automatique.\n"
  return ByteArrayOutputStream().also{out->ZipOutputStream(out).use{zip->zip.putNextEntry(ZipEntry("capture.png"));zip.write(png.toByteArray());zip.closeEntry();zip.putNextEntry(ZipEntry("diagnostic.txt"));zip.write(report.toByteArray(Charsets.UTF_8));zip.closeEntry()}}.toByteArray()
 }
}
