package com.cycling.app

import android.util.Log
import com.chaquo.python.Python
import org.json.JSONObject

object BleBridge {
    private const val TAG = "BleBridge"
    private var bridgeModule: com.chaquo.python.PyObject? = null
    lateinit var bleManager: BleManager

    fun ensureLoaded() {
        if (bridgeModule == null) {
            bridgeModule = Python.getInstance().getModule("cycling.platform.bridge")
        }
    }

    fun onBleData(data: Map<String, Any>) {
        ensureLoaded()
        val json = JSONObject(data as Map<String, *>).toString()
        bridgeModule?.callAttr("push_ble_data", json)
    }

    fun onDeviceFound(address: String, name: String, rssi: Int) {
        ensureLoaded()
        Log.d(TAG, "Device found: $name ($address) RSSI=$rssi")
        bridgeModule?.callAttr("push_device", address, name, rssi)
    }

    fun onConnected(deviceName: String) {
        ensureLoaded()
        Log.i(TAG, "Connected to $deviceName")
        bridgeModule?.callAttr("set_connected", deviceName)
    }

    fun onDisconnected() {
        ensureLoaded()
        Log.i(TAG, "Disconnected")
        bridgeModule?.callAttr("set_disconnected")
    }

    @JvmStatic
    fun connectToDevice(address: String, hrAddress: String?) {
        Log.i(TAG, "connectToDevice called from Python: $address")
        if (::bleManager.isInitialized) {
            bleManager.connect(address, hrAddress)
        } else {
            Log.e(TAG, "bleManager not initialized")
        }
    }

    @JvmStatic
    fun disconnectFromDevice() {
        Log.i(TAG, "disconnectFromDevice called from Python")
        if (::bleManager.isInitialized) {
            bleManager.disconnect()
        } else {
            Log.e(TAG, "bleManager not initialized")
        }
    }
}
