package com.cycling.app

import com.chaquo.python.Python
import org.json.JSONObject

object BleBridge {
    private var bridgeModule: com.chaquo.python.PyObject? = null

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
        bridgeModule?.callAttr("push_device", address, name, rssi)
    }

    fun onConnected(deviceName: String) {
        ensureLoaded()
        bridgeModule?.callAttr("set_connected", deviceName)
    }

    fun onDisconnected() {
        ensureLoaded()
        bridgeModule?.callAttr("set_disconnected")
    }
}
