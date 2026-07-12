import Foundation
import Security

/// 登录令牌存取:系统钥匙串(iOS 存敏感凭证的标准位置,加密落盘)。
/// 契约 2026-07-12:令牌=纯随机不透明串,长期有效;退出登录/被踢即删。
enum AuthStore {
    private static let service = "com.nuguri.FitAl"
    private static let account = "auth-token"

    static var token: String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var out: AnyObject?
        guard SecItemCopyMatching(query as CFDictionary, &out) == errSecSuccess,
              let data = out as? Data
        else { return nil }
        return String(data: data, encoding: .utf8)
    }

    static func save(_ token: String) {
        clear()
        let item: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecValueData as String: Data(token.utf8),
        ]
        SecItemAdd(item as CFDictionary, nil)
    }

    static func clear() {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        SecItemDelete(query as CFDictionary)
    }
}

extension Notification.Name {
    /// 任一业务请求 401(令牌被删/失效):接口层清令牌后广播,门卫切回登录页
    static let fitalUnauthorized = Notification.Name("fital.unauthorized")
}
