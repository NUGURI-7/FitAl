import Foundation

// 后端接口层:契约与 Web 端完全一致(/days /weights /chat)
// 开发期直连 Mac 局域网地址;后端上云后只改这一处
enum API {
    static let base = URL(string: "http://192.168.10.145:8000")!
    static let userID = 1

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

    static func fetchDay(_ dateISO: String) async throws -> APIDay {
        var url = base.appending(path: "days/\(dateISO)")
        url.append(queryItems: [URLQueryItem(name: "user_id", value: "\(userID)")])
        let (data, resp) = try await session.data(from: url)
        try Self.ensureOK(resp, data: data)
        return try decoder.decode(APIDay.self, from: data)
    }

    /// 读身体档案:头像球首字与设置页都用它
    static func fetchUser() async throws -> UserProfile {
        let url = base.appending(path: "users/\(userID)")
        let (data, resp) = try await session.data(from: url)
        try ensureOK(resp, data: data)
        return try decoder.decode(UserProfile.self, from: data)
    }

    /// 改身体档案:只发改动的字段;昵称重名后端回 409,提示语透传
    static func patchUser(_ patch: UserPatch) async throws {
        var req = URLRequest(url: base.appending(path: "users/\(userID)"))
        req.httpMethod = "PATCH"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(patch)
        let (data, resp) = try await session.data(for: req)
        try ensureOK(resp, data: data)
    }

    /// 设置页·自定义食物列表(后端按更新时间倒序)
    static func fetchUserFoods() async throws -> [UserFoodItem] {
        var url = base.appending(path: "user-foods")
        url.append(queryItems: [URLQueryItem(name: "user_id", value: "\(userID)")])
        let (data, resp) = try await session.data(from: url)
        try ensureOK(resp, data: data)
        return try decoder.decode(UserFoodsResponse.self, from: data).foods
    }

    /// 删自定义食物:只影响以后的解析,已存记录数字不动
    static func deleteUserFood(id: Int) async throws {
        var req = URLRequest(url: base.appending(path: "user-foods/\(id)"))
        req.httpMethod = "DELETE"
        let (data, resp) = try await session.data(for: req)
        try ensureOK(resp, data: data)
    }

    /// 设置页·AI 记忆列表
    static func fetchMemories() async throws -> [MemoryItem] {
        var url = base.appending(path: "memories")
        url.append(queryItems: [URLQueryItem(name: "user_id", value: "\(userID)")])
        let (data, resp) = try await session.data(from: url)
        try ensureOK(resp, data: data)
        return try decoder.decode(MemoriesResponse.self, from: data).memories
    }

    /// 删记忆:即停止注入解析
    static func deleteMemory(id: Int) async throws {
        var req = URLRequest(url: base.appending(path: "memories/\(id)"))
        req.httpMethod = "DELETE"
        let (data, resp) = try await session.data(for: req)
        try ensureOK(resp, data: data)
    }

    static func fetchWeights(days: Int = 30) async throws -> [WeightPoint] {
        var url = base.appending(path: "weights")
        url.append(queryItems: [
            URLQueryItem(name: "user_id", value: "\(userID)"),
            URLQueryItem(name: "days", value: "\(days)"),
        ])
        let (data, resp) = try await session.data(from: url)
        try Self.ensureOK(resp, data: data)
        return try decoder.decode(WeightsResponse.self, from: data).weights
    }

    /// 发一句话记录:SSE 流,取 reply 事件里的模板回执
    static func sendChat(_ text: String) async throws -> String {
        var req = URLRequest(url: base.appending(path: "chat"))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(ChatIn(userId: userID, text: text))
        req.timeoutInterval = 120

        let (bytes, resp) = try await URLSession.shared.bytes(for: req)
        if let http = resp as? HTTPURLResponse, http.statusCode >= 400 {
            throw APIError.server("发送失败(\(http.statusCode))")
        }

        var event = ""
        var reply = ""
        for try await line in bytes.lines {
            if line.hasPrefix("event:") {
                event = line.dropFirst(6).trimmingCharacters(in: .whitespaces)
            } else if line.hasPrefix("data:"), event == "reply" {
                let payload = line.dropFirst(5).trimmingCharacters(in: .whitespaces)
                if let d = payload.data(using: .utf8),
                   let obj = try? decoder.decode(ReplyData.self, from: d) {
                    reply = obj.text
                }
            }
        }
        return reply.isEmpty ? "已记录" : reply
    }

    /// 改记录:只发改动的字段;改输入量后端重算热量,直接改热量转"你报的"
    static func patchRecord(kind: String, id: Int, patch: RecordPatch) async throws {
        var req = URLRequest(url: base.appending(path: "records/\(kind)/\(id)"))
        req.httpMethod = "PATCH"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(patch)
        let (data, resp) = try await session.data(for: req)
        try ensureOK(resp, data: data)
    }

    /// 删记录:kind = food | exercise | weight;删除触发所在顿/场后端重算
    static func deleteRecord(kind: String, id: Int) async throws {
        var req = URLRequest(url: base.appending(path: "records/\(kind)/\(id)"))
        req.httpMethod = "DELETE"
        let (data, resp) = try await session.data(for: req)
        try ensureOK(resp, data: data)
    }

    private static func ensureOK(_ resp: URLResponse, data: Data) throws {
        guard let http = resp as? HTTPURLResponse, http.statusCode >= 400 else { return }
        if let detail = try? decoder.decode(ErrorDetail.self, from: data) {
            throw APIError.server(detail.detail)
        }
        throw APIError.server("请求失败(\(http.statusCode))")
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
    let userId: Int
    let text: String
    enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case text
    }
}

private struct ReplyData: Decodable { let text: String }
private struct ErrorDetail: Decodable { let detail: String }

/// 身体档案(GET /users/{id}):昵称给头像球,其余供设置页读改
struct UserProfile: Decodable {
    let id: Int
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
