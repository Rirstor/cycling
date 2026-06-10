package com.cycling.app

import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanFilter
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.content.Intent
import android.os.Build
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

    private val bluetoothAdapter: BluetoothAdapter? =
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

        val filters = listOf(
            ScanFilter.Builder()
                .setServiceUuid(android.os.ParcelUuid(FTMS_SERVICE))
                .build()
        )

        val settings = ScanSettings.Builder()
            .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
            .build()

        scanCallback = object : ScanCallback() {
            override fun onScanResult(callbackType: Int, result: ScanResult) {
                val device = result.device
                val name = device.name ?: "Unknown"
                val rssi = result.rssi
                BleBridge.onDeviceFound(device.address, name, rssi)
            }
        }

        bleScanner.startScan(filters, settings, scanCallback)
        Log.i(TAG, "BLE scanning started")
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

        // FTMS Indoor Bike Data is a packed structure of variable-length fields.
        // Every optional field must be consumed in order so the cursor stays
        // aligned for the fields that follow it. Skipping a present field (e.g.
        // average speed/cadence or resistance) corrupts the offset of power.

        // Bit 0 (More Data): when SET, Instantaneous Speed is NOT present.
        if (flags and 0x0001 == 0 && buffer.remaining() >= 2) {
            result["instantaneous_speed"] = (buffer.getShort().toInt() and 0xFFFF
                ).toDouble() / 100.0
        }

        // Bit 1: Average Speed
        if (flags and 0x0002 != 0 && buffer.remaining() >= 2) {
            result["average_speed"] = (buffer.getShort().toInt() and 0xFFFF
                ).toDouble() / 100.0
        }

        // Bit 2: Instantaneous Cadence
        if (flags and 0x0004 != 0 && buffer.remaining() >= 2) {
            result["instantaneous_cadence"] = (buffer.getShort().toInt() and 0xFFFF
                ).toDouble() / 2.0
        }

        // Bit 3: Average Cadence
        if (flags and 0x0008 != 0 && buffer.remaining() >= 2) {
            result["average_cadence"] = (buffer.getShort().toInt() and 0xFFFF
                ).toDouble() / 2.0
        }

        // Bit 4: Total Distance (uint24)
        if (flags and 0x0010 != 0 && buffer.remaining() >= 3) {
            val distance = (buffer.get().toInt() and 0xFF) or
                    ((buffer.get().toInt() and 0xFF) shl 8) or
                    ((buffer.get().toInt() and 0xFF) shl 16)
            result["total_distance"] = distance.toDouble()
        }

        // Bit 5: Resistance Level (sint16)
        if (flags and 0x0020 != 0 && buffer.remaining() >= 2) {
            result["resistance_level"] = buffer.getShort().toInt().toDouble()
        }

        // Bit 6: Instantaneous Power (sint16)
        if (flags and 0x0040 != 0 && buffer.remaining() >= 2) {
            result["instantaneous_power"] = buffer.getShort().toInt().toDouble()
        }

        // Bit 7: Average Power (sint16)
        if (flags and 0x0080 != 0 && buffer.remaining() >= 2) {
            result["average_power"] = buffer.getShort().toInt().toDouble()
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
