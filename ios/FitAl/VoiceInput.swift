import AVFoundation
import Foundation
import Observation

// 语音输入会话(iOS)· 点开点关(与 Web 一致)
// 抓麦克风 → 转 16k 单声道 16 位 PCM → WebSocket /voice 转给后端(后端再对倒豆包),
// 识别文字累计回填输入框。只做语音转文字,不碰记录。
// 令牌失效与 HTTP 401 同处理:清钥匙串令牌 + 广播,门卫整界面切回登录页。

@MainActor
@Observable
final class VoiceInput {
    enum Phase { case idle, connecting, recording, finishing }

    private(set) var phase: Phase = .idle
    private(set) var level: Double = 0
    /// 本次录音到目前为止的整句(累计全量,覆盖显示);视图 onChange 拼到已有内容后
    private(set) var transcript = ""
    /// 一次性错误提示;视图消费后置回 nil
    var errorMessage: String?

    var isActive: Bool { phase != .idle }

    private let engine = AVAudioEngine()
    private var sink: PCMSink?
    private var task: URLSessionWebSocketTask?
    private var ready = false

    func toggle() { isActive ? stop() : start() }

    // MARK: - 启动

    func start() {
        guard phase == .idle else { return }
        guard let token = AuthStore.token else { kickToLogin(); return }
        phase = .connecting
        level = 0
        transcript = ""
        ready = false
        Task { await begin(token: token) }
    }

    private func begin(token: String) async {
        guard await requestMicPermission() else {
            fail("需要麦克风权限,请在系统设置里允许")
            return
        }
        guard phase == .connecting else { return } // 期间被取消

        do {
            let sess = AVAudioSession.sharedInstance()
            try sess.setCategory(.record, mode: .default)
            try sess.setActive(true)
        } catch {
            fail("无法启用麦克风")
            return
        }

        // 采样管线:硬件格式 → 16k 单声道 16 位
        let input = engine.inputNode
        let inFormat = input.outputFormat(forBus: 0)
        guard
            let outFormat = AVAudioFormat(
                commonFormat: .pcmFormatInt16, sampleRate: 16000,
                channels: 1, interleaved: true
            ),
            let converter = AVAudioConverter(from: inFormat, to: outFormat)
        else {
            fail("音频初始化失败")
            return
        }

        // 先开连接、先把 start 排进发送队列(保证它是首帧),再开麦克风
        openSocket(token: token)

        let sink = PCMSink(converter: converter, outFormat: outFormat, task: task!) {
            lvl in
            Task { @MainActor [weak self] in self?.applyLevel(lvl) }
        }
        self.sink = sink

        input.installTap(onBus: 0, bufferSize: 2048, format: inFormat) { buffer, _ in
            sink.feed(buffer)
        }
        do {
            try engine.start()
        } catch {
            fail("麦克风启动失败")
        }
    }

    private func applyLevel(_ lvl: Double) {
        guard phase == .recording else { return }
        level = lvl
    }

    // MARK: - 停止(松手:等后端把尾段识别完再结束)

    func stop() {
        switch phase {
        case .idle, .finishing:
            return
        case .connecting where !ready:
            cancel() // 还没连上就点关:直接放弃,没录到东西
        default:
            phase = .finishing
            level = 0
            stopCapture() // 停止采集,连接留着收尾段识别与 done
            send(json: ["type": "stop"])
        }
    }

    /// 静默清理(视图消失/放弃):不出提示、不回填
    func cancel() { teardown(idle: true) }

    // MARK: - WebSocket

    private func openSocket(token: String) {
        guard let url = voiceURL() else {
            fail("语音地址无效")
            return
        }
        let t = URLSession.shared.webSocketTask(with: url)
        task = t
        t.resume()
        send(json: ["type": "start", "token": token])
        listen()
    }

    private func listen() {
        guard let task else { return }
        // Task 继承本类的主 actor;receive() 挂起不阻塞,handle/socketClosed 同 actor 直调
        Task { [weak self] in
            while true {
                do {
                    let msg = try await task.receive()
                    guard let self else { return }
                    self.handle(msg)
                } catch {
                    self?.socketClosed()
                    return
                }
            }
        }
    }

    private func handle(_ msg: URLSessionWebSocketTask.Message) {
        guard case let .string(text) = msg,
            let data = text.data(using: .utf8),
            let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
            let type = obj["type"] as? String
        else { return }

        switch type {
        case "ready":
            ready = true
            if phase == .connecting { phase = .recording }
        case "result":
            transcript = (obj["text"] as? String) ?? transcript
        case "done":
            finish()
        case "error":
            let m = (obj["message"] as? String) ?? "语音出错"
            if m.contains("未登录") {
                kickToLogin()
            } else {
                fail("语音识别出错:\(m)")
            }
        default:
            break
        }
    }

    /// 连接被动断开:有识别结果按结束处理,否则报错
    private func socketClosed() {
        guard phase != .idle else { return }
        if transcript.isEmpty {
            fail("语音连接已断开")
        } else {
            finish()
        }
    }

    private func send(json: [String: String]) {
        guard let data = try? JSONSerialization.data(withJSONObject: json),
            let str = String(data: data, encoding: .utf8)
        else { return }
        task?.send(.string(str)) { _ in }
    }

    private func voiceURL() -> URL? {
        var c = URLComponents(url: API.base, resolvingAgainstBaseURL: false)
        c?.scheme = (API.base.scheme == "https") ? "wss" : "ws"
        c?.path = "/voice"
        return c?.url
    }

    // MARK: - 收尾

    private func finish() {
        teardown(idle: true) // transcript 保留,视图已随 onChange 拼进输入框
    }

    private func fail(_ msg: String) {
        teardown(idle: true)
        errorMessage = msg
    }

    private func kickToLogin() {
        teardown(idle: true)
        AuthStore.clear()
        NotificationCenter.default.post(name: .fitalUnauthorized, object: nil)
    }

    private func stopCapture() {
        if engine.isRunning {
            engine.inputNode.removeTap(onBus: 0)
            engine.stop()
        }
        sink?.stop()
    }

    private func teardown(idle: Bool) {
        stopCapture()
        sink = nil
        task?.cancel()
        task = nil
        try? AVAudioSession.sharedInstance().setActive(
            false, options: .notifyOthersOnDeactivation)
        level = 0
        if idle { phase = .idle }
    }

    private func requestMicPermission() async -> Bool {
        await withCheckedContinuation { cont in
            if #available(iOS 17.0, *) {
                AVAudioApplication.requestRecordPermission { cont.resume(returning: $0) }
            } else {
                AVAudioSession.sharedInstance().requestRecordPermission {
                    cont.resume(returning: $0)
                }
            }
        }
    }
}

// 音频转发端:在音频回调线程上运行(与主线程隔离)。
// installTap 串行投递缓冲,内部状态仅音频线程访问;active 用锁与主线程协调,故 @unchecked Sendable。
private final class PCMSink: @unchecked Sendable {
    private let converter: AVAudioConverter
    private let outFormat: AVAudioFormat
    private let task: URLSessionWebSocketTask
    private let onLevel: @Sendable (Double) -> Void
    private let lock = NSLock()
    private var active = true

    init(
        converter: AVAudioConverter, outFormat: AVAudioFormat,
        task: URLSessionWebSocketTask, onLevel: @escaping @Sendable (Double) -> Void
    ) {
        self.converter = converter
        self.outFormat = outFormat
        self.task = task
        self.onLevel = onLevel
    }

    func stop() {
        lock.lock()
        active = false
        lock.unlock()
    }

    func feed(_ buffer: AVAudioPCMBuffer) {
        lock.lock()
        let go = active
        lock.unlock()
        guard go else { return }

        onLevel(rms(buffer))
        guard let out = convert(buffer), let data = int16Data(out) else { return }
        task.send(.data(data)) { _ in }
    }

    private func convert(_ input: AVAudioPCMBuffer) -> AVAudioPCMBuffer? {
        let ratio = outFormat.sampleRate / input.format.sampleRate
        let capacity = AVAudioFrameCount(Double(input.frameLength) * ratio) + 1024
        guard let out = AVAudioPCMBuffer(pcmFormat: outFormat, frameCapacity: capacity)
        else { return nil }
        var fed = false
        var err: NSError?
        let status = converter.convert(to: out, error: &err) { _, outStatus in
            if fed {
                outStatus.pointee = .noDataNow
                return nil
            }
            fed = true
            outStatus.pointee = .haveData
            return input
        }
        guard status != .error, out.frameLength > 0 else { return nil }
        return out
    }

    private func int16Data(_ buffer: AVAudioPCMBuffer) -> Data? {
        guard let ch = buffer.int16ChannelData else { return nil }
        return Data(bytes: ch[0], count: Int(buffer.frameLength) * MemoryLayout<Int16>.size)
    }

    private func rms(_ buffer: AVAudioPCMBuffer) -> Double {
        guard let ch = buffer.floatChannelData else { return 0 }
        let n = Int(buffer.frameLength)
        guard n > 0 else { return 0 }
        let p = ch[0]
        var sum: Float = 0
        for i in 0..<n { sum += p[i] * p[i] }
        return min(1, Double((sum / Float(n)).squareRoot()) * 3.2)
    }
}
