import SwiftUI

/// 登录页:本地无令牌/被踢下线时的全屏门面(契约 2026-07-12)。
/// 登录=昵称+密码;注册=邀请码+昵称+密码+身体档案(注册页一并填);
/// 注册成功当场发令牌,免二次登录。
/// 三层世界:纸感底+白卡片输入行,提交键=品牌绿液态玻璃。
struct LoginView: View {
    /// 登录/注册成功:门卫切回主界面
    var onAuthed: () -> Void

    @State private var isRegister = false
    @State private var nickname = ""
    @State private var password = ""
    @State private var inviteCode = ""
    @State private var height = ""
    @State private var sex = "male"
    @State private var birthYear = ""
    @State private var busy = false
    @State private var error: String?
    @State private var authCount = 0

    @FocusState private var focused: Bool
    @Namespace private var glassNS

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 8) {
                header
                modeToggle
                    .frame(maxWidth: .infinity)
                    .padding(.bottom, 10)

                if isRegister {
                    textRow(label: "邀请码", text: $inviteCode, keyboard: .asciiCapable)
                        .textInputAutocapitalization(.characters)
                    hintText("一码注册一人,用过即作废;问管理员要")
                }

                textRow(label: "昵称", text: $nickname, keyboard: .default)
                secureRow

                if isRegister {
                    if !password.isEmpty && password.count < 6 {
                        Text("密码最短 6 位")
                            .font(.system(size: 12))
                            .foregroundStyle(Theme.burn)
                            .padding(.horizontal, 4)
                    }
                    sectionHeader("身体档案")
                        .padding(.top, 8)
                    textRow(label: "身高", text: $height, keyboard: .decimalPad, unit: "cm")
                    sexRow
                    textRow(label: "出生年份", text: $birthYear, keyboard: .numberPad, unit: "年")
                    hintText("用于基础代谢与消耗计算,之后可在设置里改")
                }

                if let error {
                    Text(error)
                        .font(.system(size: 12))
                        .foregroundStyle(Theme.burn)
                        .padding(.horizontal, 4)
                }

                submitButton
                    .padding(.top, 12)

                Text(isRegister ? "注册即登录,不用再输一遍" : "没有账号?切到注册,拿邀请码进来\n忘了密码找管理员重置")
                    .font(.system(size: 11))
                    .foregroundStyle(Theme.textSecondary.opacity(0.8))
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: .infinity)
                    .padding(.top, 10)
            }
            .padding(.horizontal, 20)
            .padding(.top, 48)
            .padding(.bottom, 32)
        }
        .scrollDismissesKeyboard(.interactively)
        .background(Theme.paper.ignoresSafeArea())
        .background(brandGlow, alignment: .top)
        .toolbar {
            ToolbarItemGroup(placement: .keyboard) {
                Spacer()
                Button("完成") { focused = false }
            }
        }
        .sensoryFeedback(.success, trigger: authCount)
        .animation(.spring(duration: 0.35), value: isRegister)
    }

    // MARK: - 头部

    private var header: some View {
        VStack(spacing: 4) {
            (Text("Fit").foregroundStyle(Theme.textPrimary)
                + Text("Al").foregroundStyle(Theme.brand)
                + Text(".").foregroundStyle(Theme.burn))
                .font(.system(size: 36, weight: .bold, design: .rounded))
            Text("一句话,记下吃和练")
                .font(.system(size: 13))
                .foregroundStyle(Theme.textSecondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.bottom, 24)
    }

    /// 顶部品牌光晕:纸感体系内的柔和径向渐变(定稿:不用模糊,径向渐变代)
    private var brandGlow: some View {
        RadialGradient(
            colors: [Theme.brand.opacity(0.12), .clear],
            center: .top, startRadius: 0, endRadius: 300
        )
        .frame(height: 300)
        .ignoresSafeArea()
        .allowsHitTesting(false)
    }

    // MARK: - 登录/注册切换(与性别滑块同款液态玻璃胶囊)

    private var modeToggle: some View {
        HStack(spacing: 2) {
            modeOption(false, "登录")
            modeOption(true, "注册")
        }
        .padding(3)
        .background(Color.black.opacity(0.05), in: .capsule)
    }

    private func modeOption(_ value: Bool, _ title: String) -> some View {
        Button {
            guard isRegister != value else { return }
            withAnimation(.spring(duration: 0.35)) {
                isRegister = value
                error = nil
            }
        } label: {
            Text(title)
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(isRegister == value ? Theme.textPrimary : Theme.textSecondary)
                .padding(.horizontal, 26)
                .padding(.vertical, 7)
                .contentShape(.capsule)
        }
        .background {
            if isRegister == value {
                Color.clear
                    .glassEffect(.regular.interactive(), in: .capsule)
                    .matchedGeometryEffect(id: "mode-thumb", in: glassNS)
            }
        }
    }

    // MARK: - 行组件(与设置页同款)

    private func sectionHeader(_ title: String) -> some View {
        Text(title)
            .font(.system(size: 12, weight: .semibold))
            .foregroundStyle(Theme.textSecondary)
            .padding(.horizontal, 4)
            .padding(.top, 8)
    }

    private func hintText(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 11))
            .foregroundStyle(Theme.textSecondary.opacity(0.85))
            .padding(.horizontal, 4)
    }

    private func textRow(
        label: String, text: Binding<String>,
        keyboard: UIKeyboardType, unit: String? = nil
    ) -> some View {
        HStack {
            Text(label)
                .font(.system(size: 13))
                .foregroundStyle(Theme.textSecondary)
            Spacer()
            TextField("", text: text)
                .keyboardType(keyboard)
                .focused($focused)
                .multilineTextAlignment(.trailing)
                .font(.system(size: 16, weight: .semibold, design: keyboard == .default ? .default : .rounded))
                .foregroundStyle(Theme.textPrimary)
                .frame(maxWidth: 180)
            if let unit {
                Text(unit)
                    .font(.system(size: 11))
                    .foregroundStyle(Theme.textSecondary)
                    .frame(width: 24, alignment: .leading)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 13)
        .background(Theme.card, in: .rect(cornerRadius: 14))
    }

    private var secureRow: some View {
        HStack {
            Text("密码")
                .font(.system(size: 13))
                .foregroundStyle(Theme.textSecondary)
            Spacer()
            SecureField("", text: $password)
                .focused($focused)
                .multilineTextAlignment(.trailing)
                .font(.system(size: 16, weight: .semibold))
                .foregroundStyle(Theme.textPrimary)
                .frame(maxWidth: 180)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 13)
        .background(Theme.card, in: .rect(cornerRadius: 14))
    }

    @Namespace private var sexNS

    private var sexRow: some View {
        HStack {
            Text("性别")
                .font(.system(size: 13))
                .foregroundStyle(Theme.textSecondary)
            Spacer()
            HStack(spacing: 2) {
                sexOption("male", "男")
                sexOption("female", "女")
            }
            .padding(3)
            .background(Color.black.opacity(0.05), in: .capsule)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 9)
        .background(Theme.card, in: .rect(cornerRadius: 14))
    }

    private func sexOption(_ value: String, _ title: String) -> some View {
        Button {
            withAnimation(.spring(duration: 0.35)) { sex = value }
        } label: {
            Text(title)
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(sex == value ? Theme.textPrimary : Theme.textSecondary)
                .padding(.horizontal, 18)
                .padding(.vertical, 5)
                .contentShape(.capsule)
        }
        .background {
            if sex == value {
                Color.clear
                    .glassEffect(.regular.interactive(), in: .capsule)
                    .matchedGeometryEffect(id: "login-sex-thumb", in: sexNS)
            }
        }
    }

    // MARK: - 校验与提交

    private var trimmedNick: String { nickname.trimmingCharacters(in: .whitespaces) }

    private var valid: Bool {
        guard !trimmedNick.isEmpty, trimmedNick.count <= 50, password.count >= 6 else { return false }
        guard isRegister else { return true }
        guard !inviteCode.trimmingCharacters(in: .whitespaces).isEmpty else { return false }
        guard let h = Double(height), h > 0 else { return false }
        let thisYear = Calendar.current.component(.year, from: Date())
        guard let y = Int(birthYear), y >= 1900, y <= thisYear else { return false }
        return true
    }

    private var submitButton: some View {
        Button {
            submit()
        } label: {
            Label(
                busy ? (isRegister ? "注册中…" : "登录中…") : (isRegister ? "注册并进入" : "登录"),
                systemImage: isRegister ? "person.badge.plus" : "key.fill"
            )
            .font(.system(size: 15, weight: .semibold))
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 13)
        }
        .glassEffect(.regular.tint(Theme.brand).interactive(), in: .capsule)
        .disabled(!valid || busy)
        .opacity(valid || busy ? 1 : 0.35)
        .animation(.easeOut(duration: 0.2), value: valid)
    }

    private func submit() {
        guard valid, !busy else { return }
        focused = false
        busy = true
        error = nil
        Task {
            do {
                if isRegister {
                    try await API.register(
                        inviteCode: inviteCode.trimmingCharacters(in: .whitespaces),
                        nickname: trimmedNick,
                        password: password,
                        heightCm: Double(height) ?? 0,
                        sex: sex,
                        birthYear: Int(birthYear) ?? 0
                    )
                } else {
                    try await API.login(nickname: trimmedNick, password: password)
                }
                authCount += 1
                onAuthed()
            } catch {
                self.error = error.localizedDescription
            }
            busy = false
        }
    }
}

#Preview {
    LoginView {}
}
