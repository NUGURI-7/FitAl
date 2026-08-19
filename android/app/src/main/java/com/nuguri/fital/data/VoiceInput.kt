package com.nuguri.fital.data

import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString
import okio.ByteString.Companion.toByteString
import org.json.JSONObject
import kotlin.math.abs

/**
 * 语音输入会话(契约 WS /voice):点开点关。
 * 抓麦克风 → 16000Hz / 16 位 / 单声道裸 PCM → 逐包灌给后端(后端再对倒豆包),
 * 识别文字累计回填输入框。只做语音转文字,不碰记录。
 * 令牌失效与请求 401 同处理:清本地令牌并发信号,门卫整界面切回登录页。
 */
class VoiceInput(private val scope: CoroutineScope) {

    enum class Phase { Idle, Connecting, Recording, Finishing }

    var phase by mutableStateOf(Phase.Idle)
        private set

    /** 本次录音到目前为止的整句(后端发的是累计全量,直接覆盖) */
    var transcript by mutableStateOf("")
        private set

    /** 一次性错误提示,界面消费后置回 null */
    var error by mutableStateOf<String?>(null)

    /** 当前音量,给声波条用 */
    var level by mutableFloatStateOf(0f)
        private set

    val isActive: Boolean get() = phase != Phase.Idle

    private val client = OkHttpClient()
    private var socket: WebSocket? = null
    private var pump: Job? = null
    private var ready = false

    private companion object {
        const val URL = "wss://fital.nuguri.org/voice"
        const val SAMPLE_RATE = 16000
        const val PACKET_BYTES = 6400 // 约 200 毫秒:16000 × 2 字节 × 0.2 秒
    }

    fun toggle() {
        if (isActive) stop() else start()
    }

    fun start() {
        if (phase != Phase.Idle) return
        phase = Phase.Connecting
        transcript = ""
        level = 0f
        ready = false

        scope.launch {
            val token = AuthStore.token()
            if (token == null) {
                AuthStore.unauthorized.tryEmit(Unit)
                phase = Phase.Idle
                return@launch
            }
            connect(token)
        }
    }

    /** 松手:告诉后端说完了,等它把尾巴转完再收 */
    fun stop() {
        if (phase == Phase.Idle || phase == Phase.Finishing) return
        phase = Phase.Finishing
        pump?.cancel()
        pump = null
        socket?.send(JSONObject().put("type", "stop").toString())
    }

    /** 界面消失等场景:不等尾巴,直接收掉 */
    fun cancel() {
        pump?.cancel()
        pump = null
        socket?.close(1000, null)
        socket = null
        phase = Phase.Idle
        level = 0f
    }

    private fun connect(token: String) {
        val req = Request.Builder().url(URL).build()
        socket = client.newWebSocket(req, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                webSocket.send(
                    JSONObject().put("type", "start").put("token", token).toString()
                )
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                val obj = runCatching { JSONObject(text) }.getOrNull() ?: return
                when (obj.optString("type")) {
                    "ready" -> {
                        ready = true
                        scope.launch {
                            if (phase == Phase.Connecting) {
                                phase = Phase.Recording
                                startPump(webSocket)
                            }
                        }
                    }

                    "result" -> scope.launch { transcript = obj.optString("text", transcript) }

                    "done" -> scope.launch { finish() }

                    "error" -> {
                        val m = obj.optString("message", "语音出错")
                        scope.launch {
                            if (m.contains("未登录") || m.contains("令牌")) {
                                AuthStore.clear()
                                AuthStore.unauthorized.tryEmit(Unit)
                                cancel()
                            } else {
                                fail("语音识别出错：$m")
                            }
                        }
                    }
                }
            }

            override fun onMessage(webSocket: WebSocket, bytes: ByteString) = Unit

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                scope.launch { fail("语音连接断了：${t.message ?: "未知原因"}") }
            }

            /** 被动断开:已经有识别结果就当正常结束,否则报错 */
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                scope.launch {
                    if (phase == Phase.Idle) return@launch
                    if (transcript.isBlank()) fail("语音连接断了") else finish()
                }
            }
        })
    }

    /** 采集循环:每约 200 毫秒发一包裸 PCM,顺带算个音量给声波条 */
    private fun startPump(webSocket: WebSocket) {
        pump = scope.launch(Dispatchers.IO) {
            val minBuf = AudioRecord.getMinBufferSize(
                SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
            )
            val recorder = runCatching {
                AudioRecord(
                    MediaRecorder.AudioSource.VOICE_RECOGNITION,
                    SAMPLE_RATE,
                    AudioFormat.CHANNEL_IN_MONO,
                    AudioFormat.ENCODING_PCM_16BIT,
                    maxOf(minBuf, PACKET_BYTES * 2),
                )
            }.getOrNull()

            if (recorder == null || recorder.state != AudioRecord.STATE_INITIALIZED) {
                recorder?.release()
                withContext(Dispatchers.Main) { fail("打不开麦克风") }
                return@launch
            }

            val buf = ByteArray(PACKET_BYTES)
            runCatching {
                recorder.startRecording()
                while (isActiveJob()) {
                    val n = recorder.read(buf, 0, buf.size)
                    if (n <= 0) continue
                    webSocket.send(buf.copyOf(n).toByteString())
                    val amp = peak(buf, n)
                    withContext(Dispatchers.Main) { level = amp }
                }
            }
            runCatching { recorder.stop() }
            recorder.release()
        }
    }

    private fun CoroutineScope.isActiveJob() = pump?.isActive == true

    /** 取这一包的峰值,归一到 0..1 */
    private fun peak(buf: ByteArray, n: Int): Float {
        var max = 0
        var i = 0
        while (i + 1 < n) {
            val v = abs((buf[i].toInt() and 0xFF) or (buf[i + 1].toInt() shl 8))
            if (v > max) max = v
            i += 2
        }
        return (max / 32768f).coerceIn(0f, 1f)
    }

    private fun finish() {
        pump?.cancel()
        pump = null
        socket?.close(1000, null)
        socket = null
        phase = Phase.Idle
        level = 0f
    }

    private fun fail(msg: String) {
        error = msg
        finish()
    }
}
