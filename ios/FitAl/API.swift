import Foundation

// 后端接口层:契约与 Web 端完全一致(/days /weights /chat)
// 开发期直连 Mac 局域网地址;后端上云后只改这一处
// 登录改造(契约 2026-07-12):身份来自 Bearer 令牌,不再明报 user_id
enum API {
    static let base = URL(string: "http://192.168.10.145:8000")!

    private static let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }()

    /// 读接口专用会话:10 秒连不上就报错进重试页,绝不无限等(假死的根源)
    private static let session: URLSession = {
        let cfg = URLSessionConfiguration.default
        cfg.timeoutIntervalForRequest = 10
        return URLSession(configuration: cfg)
    }()

    /// 统一构造请求:自动带上钥匙串里的令牌
    private static func request(
        _ path: String, method: String = "GET",
        query: [URLQueryItem] = [], body: Data? = nil
    ) -> URLRequest {
        var url = base.appending(path: path)
        if !query.isEmpty { url.append(queryItems: query) }
        var req = URLRequest(url: url)
        req.httpMethod = method
        if let token = AuthStore.token {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        if let body {
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = body
        }
        return req
    }

    static func fetchDay(_ dateISO: String) async throws -> APIDay {
        let (data, resp) = try await session.data(for: request("days/\(dateISO)"))
        try Self.ensureOK(resp, data: data)
        return try decoder.decode(APIDay.self, from: data)
    }

    /// 读身体档案:头像球首字与设置页都用它
    static func fetchUser() async throws -> UserProfile {
        let (data, resp) = try await session.data(for: request("users/me"))
        try ensureOK(resp, data: data)
        return try decoder.decode(UserProfile.self, from: data)
    }

    /// 改身体档案:只发改动的字段;昵称重名后端回 409,提示语透传
    static func patchUser(_ patch: UserPatch) async throws {
        let req = request("users/me", method: "PATCH", body: try JSONEncoder().encode(patch))
        let (data, resp) = try await session.data(for: req)
        try ensureOK(resp, data: data)
    }

    /// 设置页·自定义食物列表(后端按更新时间倒序)
    static func fetchUserFoods() async throws -> [UserFoodItem] {
        let (data, resp) = try await session.data(for: request("user-foods"))
        try ensureOK(resp, data: data)
        return try decoder.decode(UserFoodsResponse.self, from: data).foods
    }

    /// 删自定义食物:只影响以后的解析,已存记录数字不动
    static func deleteUserFood(id: Int) async throws {
        let (data, resp) = try await session.data(for: request("user-foods/\(id)", method: "DELETE"))
        try ensureOK(resp, data: data)
    }

    /// 设置页·AI 记忆列表
    static func fetchMemories() async throws -> [MemoryItem] {
        let (data, resp) = try await session.data(for: request("memories"))
        try ensureOK(resp, data: data)
        return try decoder.decode(MemoriesResponse.self, from: data).memories
    }

    /// 删记忆:即停止注入解析
    static func deleteMemory(id: Int) async throws {
        let (data, resp) = try await session.data(for: request("memories/\(id)", method: "DELETE"))
        try ensureOK(resp, data: data)
    }

    static func fetchWeights(days: Int = 30) async throws -> [WeightPoint] {
        let req = request("weights", query: [URLQueryItem(name: "days", value: "\(days)")])
        let (data, resp) = try await session.data(for: req)
        try Self.ensureOK(resp, data: data)
        return try decoder.decode(WeightsResponse.self, from: data).weights
    }

    // MARK: - 登录/注册/退出(契约 2026-07-12)

    private struct AuthResponse: Decodable { let token: String }

    /// 登录:用户名+密码(2026-07-12 拆分,昵称只做显示);
    /// 成功即把令牌收进钥匙串,失败后端统一回"用户名或密码不对"
    static func login(username: String, password: String) async throws {
        let body = try JSONEncoder().encode(["username": username, "password": password])
        let req = request("auth/login", method: "POST", body: body)
        let (data, resp) = try await session.data(for: req)
        try ensureOK(resp, data: data, kickOn401: false) // 密码不对是业务错误,不触发踢回
        AuthStore.save(try decoder.decode(AuthResponse.self, from: data).token)
    }

    /// 注册:邀请码+用户名+昵称(空=用用户名)+密码+身体档案;成功当场发令牌,免二次登录
    static func register(
        inviteCode: String, username: String, nickname: String?, password: String,
        heightCm: Double, sex: String, birthYear: Int
    ) async throws {
        struct RegisterIn: Encodable {
            let inviteCode: String, username: String, nickname: String?, password: String
            let heightCm: Double, sex: String, birthYear: Int
            enum CodingKeys: String, CodingKey {
                case username, nickname, password, sex
                case inviteCode = "invite_code"
                case heightCm = "height_cm"
                case birthYear = "birth_year"
            }
        }
        let body = try JSONEncoder().encode(RegisterIn(
            inviteCode: inviteCode, username: username, nickname: nickname, password: password,
            heightCm: heightCm, sex: sex, birthYear: birthYear
        ))
        let req = request("auth/register", method: "POST", body: body)
        let (data, resp) = try await session.data(for: req)
        try ensureOK(resp, data: data, kickOn401: false)
        AuthStore.save(try decoder.decode(AuthResponse.self, from: data).token)
    }

    /// 退出登录:服务器删本枚令牌(幂等);服务器不可达也照样清本地
    static func logout() async {
        let req = request("auth/logout", method: "POST")
        _ = try? await session.data(for: req)
        AuthStore.clear()
    }

    /// 发一句话记录:SSE 流,取 reply 事件里的模板回执与可能的澄清请求;
    /// 状态事件(event:status)按到达顺序回调给 onStatus,过程面板消费
    static func sendChat(
        _ text: String,
        onStatus: (@Sendable (ChatStatus) -> Void)? = nil
    ) async throws -> ChatOutcome {
        var req = request("chat", method: "POST", body: try JSONEncoder().encode(ChatIn(text: text)))
        req.timeoutInterval = 120

        let (bytes, resp) = try await URLSession.shared.bytes(for: req)
        if let http = resp as? HTTPURLResponse, http.statusCode == 401 {
            kickToLogin()
            throw APIError.server("登录已失效,请重新登录")
        }
        if let http = resp as? HTTPURLResponse, http.statusCode >= 400 {
            throw APIError.server("发送失败(\(http.statusCode))")
        }

        var event = ""
        var reply = ""
        var clarify: ChatClarify?
        for try await line in bytes.lines {
            if line.hasPrefix("event:") {
                event = line.dropFirst(6).trimmingCharacters(in: .whitespaces)
            } else if line.hasPrefix("data:") {
                let payload = line.dropFirst(5).trimmingCharacters(in: .whitespaces)
                guard let d = payload.data(using: .utf8) else { continue }
                if event == "reply", let obj = try? decoder.decode(ReplyData.self, from: d) {
                    reply = obj.text
                } else if event == "status",
                          let s = try? decoder.decode(ChatStatus.self, from: d) {
                    onStatus?(s) // 状态事件坏了不影响主链路(解码失败静默跳过)
                } else if event == "clarify",
                          let c = try? decoder.decode(ChatClarify.self, from: d) {
                    clarify = c // 澄清事件坏了同理:该段留在服务器待补,不伤主链路
                }
            }
        }
        return ChatOutcome(reply: reply.isEmpty ? "已记录" : reply, clarify: clarify)
    }

    /// 澄清补交(契约 2026-07-12):答案填进服务器存着的半成品,
    /// 纯代码续算入库(零 AI,毫秒级),返回回执文字。
    /// 400=没填够/乱填(带缺啥),409=已补过/不在待补态,提示语透传
    static func submitClarify(inputId: Int, answers: [String: Double]) async throws -> String {
        struct ClarifyIn: Encodable { let answers: [String: Double] }
        struct ClarifyOut: Decodable { let reply: String }
        let req = request(
            "inputs/\(inputId)/clarify", method: "POST",
            body: try JSONEncoder().encode(ClarifyIn(answers: answers))
        )
        let (data, resp) = try await session.data(for: req)
        try ensureOK(resp, data: data)
        return (try? decoder.decode(ClarifyOut.self, from: data).reply) ?? "已记录"
    }

    /// 改记录:只发改动的字段;改输入量后端重算热量,直接改热量转"你报的"
    static func patchRecord(kind: String, id: Int, patch: RecordPatch) async throws {
        let req = request("records/\(kind)/\(id)", method: "PATCH", body: try JSONEncoder().encode(patch))
        let (data, resp) = try await session.data(for: req)
        try ensureOK(resp, data: data)
    }

    /// 删记录:kind = food | exercise | weight;删除触发所在顿/场后端重算
    static func deleteRecord(kind: String, id: Int) async throws {
        let (data, resp) = try await session.data(for: request("records/\(kind)/\(id)", method: "DELETE"))
        try ensureOK(resp, data: data)
    }

    /// 401 守卫(契约 2026-07-12 第二道):清本地令牌并广播,门卫整界面切回登录页;
    /// 登录/注册自身的 401 是业务错误(密码不对),传 kickOn401: false 豁免
    private static func ensureOK(_ resp: URLResponse, data: Data, kickOn401: Bool = true) throws {
        guard let http = resp as? HTTPURLResponse, http.statusCode >= 400 else { return }
        if http.statusCode == 401 && kickOn401 {
            kickToLogin()
            throw APIError.server("登录已失效,请重新登录")
        }
        if let detail = try? decoder.decode(ErrorDetail.self, from: data) {
            throw APIError.server(detail.detail)
        }
        throw APIError.server("请求失败(\(http.statusCode))")
    }

    private static func kickToLogin() {
        AuthStore.clear()
        Task { @MainActor in
            NotificationCenter.default.post(name: .fitalUnauthorized, object: nil)
        }
    }
}

/// PATCH 请求体:字段全部可空,只编码提供了的字段
struct RecordPatch: Encodable {
    var grams: Double?
    var kcal: Double?
    var durationMin: Double?
    var loadKg: Double?
    var reps: Int?
    var weightKg: Double?

    enum CodingKeys: String, CodingKey {
        case grams, kcal, reps
        case durationMin = "duration_min"
        case loadKg = "load_kg"
        case weightKg = "weight_kg"
    }
}

enum APIError: LocalizedError {
    case server(String)
    var errorDescription: String? {
        if case let .server(msg) = self { return msg }
        return nil
    }
}

// MARK: - 响应模型(字段与后端契约一一对应)

private struct ChatIn: Encodable {
    let text: String
}

private struct ReplyData: Decodable { let text: String }

/// /chat 状态事件(契约 event:status):处理进度,纯增量
/// stage: triage / extract(带 tracks)/ track_done(带 track)/ saving
struct ChatStatus: Decodable, Sendable {
    let stage: String
    var tracks: [String]?
    var track: String?
}

/// /chat 澄清事件里的一个问题:固定=一句问话+数字输入框+单位,不做通用表单
struct ClarifyQuestion: Decodable, Sendable, Equatable {
    let key: String
    let prompt: String
    let unit: String
    let required: Bool
}

/// /chat 澄清事件(契约 event:clarify,2026-07-12):运动段缺数,
/// 该段挂起在服务器待补,前端弹小表单补交
struct ChatClarify: Decodable, Sendable, Equatable {
    let inputId: Int
    let text: String
    let questions: [ClarifyQuestion]
    /// 至少填几个(次数/时长两问一组答其一即可)
    let minAnswers: Int
}

/// 一次发送的完整结果:模板回执 + 可能的澄清请求
struct ChatOutcome: Sendable {
    let reply: String
    let clarify: ChatClarify?
}
private struct ErrorDetail: Decodable { let detail: String }

/// 身体档案(GET /users/me):昵称给头像球,其余供设置页读改
struct UserProfile: Decodable {
    let id: Int
    /// 登录标识,只读展示,不可改(2026-07-12 与昵称拆分)
    let username: String?
    let nickname: String
    let heightCm: Double
    let sex: String
    let birthYear: Int
}

/// PATCH /users/{id} 请求体:字段全部可空,只编码改动了的字段
struct UserPatch: Encodable {
    var nickname: String?
    var heightCm: Double?
    var sex: String?
    var birthYear: Int?

    enum CodingKeys: String, CodingKey {
        case nickname, sex
        case heightCm = "height_cm"
        case birthYear = "birth_year"
    }

    var isEmpty: Bool {
        nickname == nil && heightCm == nil && sex == nil && birthYear == nil
    }
}

/// 自定义食物(每100克口径,与官方表同构)
struct UserFoodItem: Decodable, Identifiable {
    let id: Int
    let name: String
    let form: String?
    let kcal: Double
    let updatedAt: String

    var at: Date { parseISOTimestamp(updatedAt) ?? .distantPast }
}

private struct UserFoodsResponse: Decodable { let foods: [UserFoodItem] }

/// AI 记忆(kind: alias 叫法 | habit 习惯 | correction 纠正)
struct MemoryItem: Decodable, Identifiable {
    let id: Int
    let kind: String
    let content: String
    let updatedAt: String

    var at: Date { parseISOTimestamp(updatedAt) ?? .distantPast }
}

private struct MemoriesResponse: Decodable { let memories: [MemoryItem] }

/// ISO 时间戳解析(带/不带小数秒两种格式都收)
func parseISOTimestamp(_ s: String) -> Date? {
    let f1 = ISO8601DateFormatter()
    f1.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    if let d = f1.date(from: s) { return d }
    return ISO8601DateFormatter().date(from: s)
}

struct APIDay: Decodable {
    let date: String
    let intakeKcal: Double
    let burnKcal: Double
    let bmrKcal: Double?
    let burnNetKcal: Double
    let weight: Double?
    let meals: [APIGroup<MealEntry>]
    let sessions: [APIGroup<ExerciseItem>]
}

struct APIGroup<T: Decodable>: Decodable, Identifiable {
    let id: Int
    let name: String?
    let start: String
    let end: String
    let kcalTotal: Double
    let items: [T]
}

struct FoodItem: Decodable, Identifiable {
    let id: Int
    let foodName: String
    let kcal: Double
    let grams: Double?
    let protein: Double?
    let fat: Double?
    let cho: Double?
    let fiber: Double?
    let source: String
}

struct Dish: Decodable {
    let dishName: String
    let totalGrams: Double
    let kcalTotal: Double
    let items: [FoodItem]
}

/// 餐次明细两种形态:单品 / 菜(成分归拢)
enum MealEntry: Decodable, Identifiable {
    case food(FoodItem)
    case dish(Dish)

    var id: String {
        switch self {
        case .food(let f): "food-\(f.id)"
        case .dish(let d): "dish-\(d.dishName)-\(d.items.first?.id ?? 0)"
        }
    }

    private enum TypeKey: String, CodingKey { case type }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: TypeKey.self)
        let type = try c.decode(String.self, forKey: .type)
        if type == "dish" {
            self = .dish(try Dish(from: decoder))
        } else {
            self = .food(try FoodItem(from: decoder))
        }
    }
}

struct ExerciseItem: Decodable, Identifiable {
    let id: Int
    let exerciseName: String
    let kcal: Double
    let kcalNet: Double?
    let durationMin: Double?
    let loadKg: Double?
    let reps: Int?
    let source: String
}

struct WeightPoint: Decodable, Identifiable {
    let id: Int
    let weightKg: Double
    let createdAt: String

    var at: Date { Self.parseISO(createdAt) ?? .distantPast }

    private static func parseISO(_ s: String) -> Date? {
        let f1 = ISO8601DateFormatter()
        f1.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let d = f1.date(from: s) { return d }
        let f2 = ISO8601DateFormatter()
        return f2.date(from: s)
    }
}

private struct WeightsResponse: Decodable {
    let weights: [WeightPoint]
}

// MARK: - 食物名展示清理(移植自 Web,同一套术语规则)

/// 该括号片段是否为可丢弃的成分表编制术语
private func isJargon(_ seg: String) -> Bool {
    if seg == "代表值" || seg == "特等" { return true }
    if seg.wholeMatch(of: /标[一二三四]/) != nil { return true }
    if seg.wholeMatch(of: /(?i)fat\d+(\.\d+)?g/) != nil { return true }
    return false
}

/// 列表展示名:去掉括号里的纯术语,括号清空则连括号去掉;完整学名另行保留
func cleanFoodName(_ raw: String) -> String {
    raw.replacing(/[（(]([^）)]*)[）)]/) { match in
        let kept = String(match.output.1)
            .split(whereSeparator: { $0 == "," || $0 == "，" })
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty && !isJargon($0) }
        return kept.isEmpty ? "" : "(\(kept.joined(separator: "，")))"
    }
    .trimmingCharacters(in: .whitespaces)
}
