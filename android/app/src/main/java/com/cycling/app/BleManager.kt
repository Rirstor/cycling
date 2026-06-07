package com.cycling.app

import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.os.Handler
import android.os.Looper
import android.util.Log
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.UUID

class BleManager(private val context: Context) {
    companion object {
        private const val TAG = "BleManager"

        val FTMS_SERVICE = UUID.fromString("00001826-0000-1000-8000-00805f9b34fb")
        val INDOOR_BIKE_DATA = UUID.fromString("00002ad2-0000-1000-8000-00805f9b34fb")
        val HEART_RATE_SERVICE = UUID.fromString("0000180d-0000-1000-8000-00805f9b34fb")
        val HEART_RATE_MEASUREMENT = UUID.fromString("00002a37-0000-1000-8000-00805f9b34fb")
    }

    val bluetoothAdapter: BluetoothAdapter? =
        (context.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager)?.adapter

    private val bleScanner = bluetoothAdapter?.bluetoothLeScanner
    private var scanCallback: ScanCallback? = null

    private var trainerGatt: BluetoothGatt? = null
    private var hrGatt: BluetoothGatt? = null

    private val mainHandler = Handler(Looper.getMainLooper())

    fun initialize() {
        if (bluetoothAdapter == null || !bluetoothAdapter.isEnabled) {
            Log.w(TAG, "Bluetooth not available or disabled")
            return
        }
        Log.i(TAG, "Bluetooth initialized")
    }

    fun startScanning() {
        if (bleScanner == null) return

        val settings = ScanSettings.Builder()
            .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
            .build()

        scanCallback = object : ScanCallback() {
            override fun onScanResult(callbackType: Int, result: ScanResult) {
                val device = result.device
                val name = device.name ?: return
                val rssi = result.rssi
                if (isCyclingDevice(name, result)) {
                    BleBridge.onDeviceFound(device.address, name, rssi)
                }
            }
        }

        bleScanner.startScan(null, settings, scanCallback)
        Log.i(TAG, "BLE scanning started (unfiltered)")
    }

    private fun isCyclingDevice(name: String, result: ScanResult): Boolean {
        val lower = name.lowercase()
        val cyclingKeywords = listOf(
            "kickr", "tacx", "neo", "suito", "wahoo", "elite",
            "zwift", "hub", "hammer", "h3", "flux", "snap",
            "dragon", "stages", "garmin", "assist"
        )
        if (cyclingKeywords.any { lower.contains(it) }) return true

        val serviceUuids = result.scanRecord?.serviceUuids ?: return false
        val cyclingServiceUuids = setOf(
            UUID.fromString("00001826-0000-1000-8000-00805f9b34fb"),
            UUID.fromString("00001818-0000-1000-8000-00805f9b34fb"),
            UUID.fromString("00001816-0000-1000-8000-00805f9b34fb"),
            UUID.fromString("0000180d-0000-1000-8000-00805f9b34fb"),
            UUID.fromString("0000180f-0000-1000-8000-00805f9b34fb"),
        )
        return serviceUuids.any { it in cyclingServiceUuids }
    }

    fun stopScanning() {
        scanCallback?.let { bleScanner?.stopScan(it) }
        scanCallback = null
    }

    fun connect(address: String, hrAddress: String? = null) {
        connectTrainer(address)
        if (hrAddress != null) {
            connectHrMonitor(hrAddress)
        }
    }

    private fun connectTrainer(address: String) {
        val device = bluetoothAdapter?.getRemoteDevice(address) ?: return
        trainerGatt = device.connectGatt(context, false, trainerGattCallback)
        Log.i(TAG, "Connecting to trainer: $address")
    }

    private fun connectHrMonitor(address: String) {
        val device = bluetoothAdapter?.getRemoteDevice(address) ?: return
        hrGatt = device.connectGatt(context, false, hrGattCallback)
        Log.i(TAG, "Connecting to HR monitor: $address")
    }

    private val trainerGattCallback = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(gatt: BluetoothGatt, status: Int, newState: Int) {
            when (newState) {
                BluetoothProfile.STATE_CONNECTED -> {
                    Log.i(TAG, "Trainer connected")
                    gatt.discoverServices()
                }
                BluetoothProfile.STATE_DISCONNECTED -> {
                    Log.i(TAG, "Trainer disconnected")
                    BleBridge.onDisconnected()
                }
            }
        }

        override fun onServicesDiscovered(gatt: BluetoothGatt, status: Int) {
            if (status != BluetoothGatt.GATT_SUCCESS) return

            val ftmsService = gatt.getService(FTMS_SERVICE) ?: return
            val bikeDataChar = ftmsService.getCharacteristic(INDOOR_BIKE_DATA) ?: return

            val success = gatt.setCharacteristicNotification(bikeDataChar, true)
            if (success) {
                Log.i(TAG, "Subscribed to Indoor Bike Data notifications")
                val deviceName = gatt.device.name ?: gatt.device.address
                BleBridge.onConnected(deviceName)
            }
        }

        override fun onCharacteristicChanged(
            gatt: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic
        ) {
            if (characteristic.uuid == INDOOR_BIKE_DATA) {
                val data = parseIndoorBikeData(characteristic.value)
                BleBridge.onBleData(data)
            }
        }
    }

    private val hrGattCallback = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(gatt: BluetoothGatt, status: Int, newState: Int) {
            if (newState == BluetoothProfile.STATE_CONNECTED) {
                gatt.discoverServices()
            }
        }

        override fun onServicesDiscovered(gatt: BluetoothGatt, status: Int) {
            if (status != BluetoothGatt.GATT_SUCCESS) return
            val hrService = gatt.getService(HEART_RATE_SERVICE) ?: return
            val hrChar = hrService.getCharacteristic(HEART_RATE_MEASUREMENT) ?: return
            gatt.setCharacteristicNotification(hrChar, true)
        }

        override fun onCharacteristicChanged(
            gatt: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic
        ) {
            if (characteristic.uuid == HEART_RATE_MEASUREMENT) {
                val hr = parseHeartRate(characteristic.value)
                BleBridge.onBleData(mapOf("heart_rate" to hr.toDouble()))
            }
        }
    }

    fun disconnect() {
        stopScanning()

        hrGatt?.let {
            try {
                it.disconnect()
            } catch (_: Exception) {}
            try {
                it.close()
            } catch (_: Exception) {}
        }
        hrGatt = null

        trainerGatt?.let {
            try {
                it.disconnect()
            } catch (_: Exception) {}
            try {
                it.close()
            } catch (_: Exception) {}
        }
        trainerGatt = null

        BleBridge.onDisconnected()
        Log.i(TAG, "Disconnected")
    }

    fun shutdown() {
        disconnect()
    }

    private fun parseIndoorBikeData(data: ByteArray): Map<String, Any> {
        val result = mutableMapOf<String, Any>()
        if (data.size < 2) return result

        val buffer = ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN)
        val flags = buffer.getShort().toInt() and 0xFFFF
        var offset = 2

        if (buffer.remaining() >= 2) {
            result["instantaneous_speed"] = (buffer.getShort().toInt() and 0xFFFF
                ).toDouble() / 100.0
            offset += 2
        }

        if (flags and 0x0004 != 0 && buffer.remaining() >= 2) {
            result["instantaneous_cadence"] = (buffer.getShort().toInt() and 0xFFFF
                ).toDouble() / 2.0
        }

        if (flags and 0x0010 != 0 && buffer.remaining() >= 3) {
            val distance = (buffer.get().toInt() and 0xFF) or
                    ((buffer.get().toInt() and 0xFF) shl 8) or
                    ((buffer.get().toInt() and 0xFF) shl 16)
            result["total_distance"] = distance.toDouble()
        }

        if (flags and 0x0040 != 0 && buffer.remaining() >= 2) {
            result["instantaneous_power"] = (buffer.getShort().toInt() and 0xFFFF).toDouble()
        }

        return result
    }

    private fun parseHeartRate(data: ByteArray): Int {
        if (data.isEmpty()) return 0
        val flags = data[0].toInt() and 0xFF
        return if (flags and 0x01 != 0) {
            (data[1].toInt() and 0xFF) or ((data[2].toInt() and 0xFF) shl 8)
        } else {
            data[1].toInt() and 0xFF
        }
    }
}
