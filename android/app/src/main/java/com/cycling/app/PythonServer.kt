package com.cycling.app

import android.util.Log
import com.chaquo.python.Python
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL

class PythonServer(
    private val context: android.content.Context,
    private val dataDir: String
) {
    private var thread: Thread? = null
    private var running = false

    fun start() {
        if (running) return
        running = true

        thread = Thread(
            {
                try {
                    Python.getInstance()
                        .getModule("cycling.web.server")
                        .callAttr("main_android", dataDir)
                } catch (e: Exception) {
                    Log.e("PythonServer", "Python server exited", e)
                } finally {
                    running = false
                }
            },
            "python-server"
        ).also { it.isDaemon = true }.apply { start() }

        Log.i("PythonServer", "Python server thread started")
    }

    suspend fun waitForReady(timeoutMs: Long = 10_000) {
        withContext(Dispatchers.IO) {
            val deadline = System.currentTimeMillis() + timeoutMs
            var lastError: String? = null

            while (System.currentTimeMillis() < deadline) {
                try {
                    val conn =
                        URL("http://127.0.0.1:8080/health").openConnection() as HttpURLConnection
                    conn.connectTimeout = 500
                    conn.readTimeout = 500
                    if (conn.responseCode == 200) {
                        Log.i("PythonServer", "Server ready")
                        return@withContext
                    }
                } catch (e: java.net.ConnectException) {
                    lastError = "Connecting..."
                } catch (e: Exception) {
                    lastError = e.message
                }
                Thread.sleep(250)
            }
            Log.w("PythonServer", "Server not ready after ${timeoutMs}ms: $lastError")
        }
    }

    fun stop() {
        running = false
        thread?.interrupt()
        thread = null
        Log.i("PythonServer", "Python server stopped")
    }
}
