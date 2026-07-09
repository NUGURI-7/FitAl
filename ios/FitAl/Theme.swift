import SwiftUI

// 设计规范定稿色(docs/context.md 2026-07-09):品牌深墨绿,数据三色低饱和,纸感底
enum Theme {
    static let brand = Color(red: 0x2F / 255, green: 0x6B / 255, blue: 0x53 / 255)
    static let intake = brand
    static let burn = Color(red: 0.85, green: 0.47, blue: 0.22)
    static let weight = Color(red: 0.32, green: 0.47, blue: 0.66)

    static let paper = Color(red: 0.969, green: 0.961, blue: 0.945)
    static let card = Color.white
    static let textPrimary = Color(red: 0.13, green: 0.13, blue: 0.12)
    static let textSecondary = Color(red: 0.45, green: 0.44, blue: 0.42)
}

// 按压回弹:所有可点元素统一手感
struct PressableStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.96 : 1)
            .animation(.spring(duration: 0.25), value: configuration.isPressed)
    }
}
