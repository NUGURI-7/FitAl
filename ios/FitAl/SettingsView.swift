import SwiftUI

// 独立设置页:系统推入(从右滑入,自带返回),主页原地保留状态
// 三块内容与 Web 对齐:身体档案读改 / 自定义食物查删 / AI 记忆查删
// 玻璃用法遵循三层世界:输入行=白卡片(内容层),控件(性别滑块/保存键/回执)=液态玻璃
struct SettingsView: View {
    let profile: UserProfile
    /// 保存成功后回调主页:球上首字与现算数字跟新
    var onSaved: () async -> Void
    /// 退出登录后回调门卫:整界面切回登录页
    var onLogout: () -> Void

    // 保存成功后基线更新,按钮回到"无改动"灰态
    @State private var baseline: UserProfile
    @State private var nickname: String
    @State private var height: String
    @State private var sex: String
    @State private var birthYear: String

    @State private var busy = false
    @State private var error: String?
    @State private var toast: String?
    @State private var saveCount = 0

    // 自定义食物列表(nil=加载中)
    @State private var foods: [UserFoodItem]?
    @State private var foodsError: String?
    @State private var foodArmedID: Int?
    @State private var foodBusy = false

    // AI 记忆列表
    @State private var memories: [MemoryItem]?
    @State private var memoriesError: String?
    @State private var memoryArmedID: Int?
    @State private var memoryBusy = false

    @State private var deleteCount = 0

    @FocusState private var focused: Bool

    init(
        profile: UserProfile,
        onSaved: @escaping () async -> Void,
        onLogout: @escaping () -> Void
    ) {
        self.profile = profile
        self.onSaved = onSaved
        self.onLogout = onLogout
        _baseline = State(initialValue: profile)
        _nickname = State(initialValue: profile.nickname)
        _height = State(initialValue: profile.heightCm.cleanString)
        _sex = State(initialValue: profile.sex)
        _birthYear = State(initialValue: String(profile.birthYear))
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 8) {
                sectionHeader("身体档案")

                VStack(spacing: 8) {
                    readOnlyRow(label: "用户名", value: profile.username ?? "—")
                    textRow(label: "昵称", text: $nickname, keyboard: .default)
                    textRow(label: "身高", text: $height, keyboard: .decimalPad, unit: "cm")
                    sexRow
                    textRow(label: "出生年份", text: $birthYear, keyboard: .numberPad, unit: "年")
                    readOnlyRow(label: "用户 ID", value: "\(profile.id)")
                }

                Text("用户名是登录标识,不可改;昵称随便改、可重名。身高、性别、出生年份用于基础代谢与消耗计算;改档案不影响已存的记录,汇总里现算的数字会自动按新档案计。")
                    .font(.system(size: 11))
                    .foregroundStyle(Theme.textSecondary.opacity(0.85))
                    .padding(.horizontal, 4)
                    .padding(.top, 2)

                if let error {
                    Text(error)
                        .font(.system(size: 12))
                        .foregroundStyle(Theme.burn)
                        .padding(.horizontal, 4)
                }

                saveButton
                    .padding(.top, 8)

                sectionHeader("自定义食物")
                    .padding(.top, 16)
                foodsSection

                sectionHeader("AI 记忆")
                    .padding(.top, 16)
                memoriesSection

                sectionHeader("账号")
                    .padding(.top, 16)
                logoutButton
                hintText("只下线这台设备,数据都在云端;重新登录即可回来。")
            }
            .padding(.horizontal, 16)
            .padding(.top, 12)
            .padding(.bottom, 32)
        }
        .task {
            async let f: Void = loadFoods()
            async let m: Void = loadMemories()
            _ = await (f, m)
        }
        .scrollDismissesKeyboard(.interactively)
        .background(Theme.paper.ignoresSafeArea())
        .navigationTitle("设置")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItemGroup(placement: .keyboard) {
                Spacer()
                Button("完成") { focused = false }
            }
        }
        .overlay(alignment: .bottom) {
            if let toast {
                Text(toast)
                    .font(.system(size: 13))
                    .foregroundStyle(Theme.textPrimary)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                    .glassEffect()
                    .padding(.bottom, 24)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
            }
        }
        .animation(.spring(duration: 0.4), value: toast)
        .sensoryFeedback(.success, trigger: saveCount)
        .sensoryFeedback(.impact, trigger: deleteCount)
    }

    // MARK: - 自定义食物

    @ViewBuilder
    private var foodsSection: some View {
        if let foods {
            if foods.isEmpty {
                emptyCard("还没有自定义食物,对话里说\n「记住蛋白粉一勺30克120千卡」就能添加\n改过 AI 估算的热量后,也会自动记在这里")
            } else {
                VStack(spacing: 8) {
                    ForEach(foods) { foodRow($0) }
                }
                hintText("想改数值:对话里再「记住」一遍同名食物即可覆盖。删除只影响以后的解析,已记的饭菜数字不变。")
            }
        } else if foodsError == nil {
            loadingText
        }
        if let foodsError {
            Text(foodsError)
                .font(.system(size: 12))
                .foregroundStyle(Theme.burn)
                .padding(.horizontal, 4)
        }
    }

    private func foodRow(_ f: UserFoodItem) -> some View {
        HStack(spacing: 10) {
            VStack(alignment: .leading, spacing: 2) {
                HStack(alignment: .firstTextBaseline, spacing: 4) {
                    Text(f.name)
                        .font(.system(size: 14, weight: .medium))
                        .foregroundStyle(Theme.textPrimary)
                        .lineLimit(1)
                    if let form = f.form {
                        Text(form)
                            .font(.system(size: 11))
                            .foregroundStyle(Theme.textSecondary)
                    }
                }
                Text("\(monthDay(f.at)) 记")
                    .font(.system(size: 11))
                    .foregroundStyle(Theme.textSecondary)
            }
            Spacer()
            HStack(alignment: .firstTextBaseline, spacing: 2) {
                Text(f.displayKcal.cleanString)
                    .font(.system(size: 14, weight: .semibold, design: .rounded))
                    .foregroundStyle(Theme.textPrimary)
                Text(f.displayUnit)
                    .font(.system(size: 10))
                    .foregroundStyle(Theme.textSecondary)
            }
            deleteButton(armed: foodArmedID == f.id, disabled: foodBusy) {
                removeFood(f)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(Theme.card, in: .rect(cornerRadius: 14))
    }

    private func removeFood(_ f: UserFoodItem) {
        guard foodArmedID == f.id else {
            arm(id: f.id, current: $foodArmedID)
            return
        }
        foodArmedID = nil
        foodBusy = true
        foodsError = nil
        Task {
            do {
                try await API.deleteUserFood(id: f.id)
                deleteCount += 1
                await loadFoods()
            } catch {
                foodsError = "删除失败:\(error.localizedDescription)"
            }
            foodBusy = false
        }
    }

    private func loadFoods() async {
        foodsError = nil
        do { foods = try await API.fetchUserFoods() } catch {
            foodsError = "加载失败:\(error.localizedDescription)"
        }
    }

    // MARK: - AI 记忆

    @ViewBuilder
    private var memoriesSection: some View {
        if let memories {
            if memories.isEmpty {
                emptyCard("还没有记忆,对话里说\n「记住我一勺是30克」这类话就会长出来")
            } else {
                VStack(spacing: 8) {
                    ForEach(memories) { memoryRow($0) }
                }
                hintText("记忆会注入每次解析,错的会持续误导,删掉即止。「纠正」是你改删 AI 估算记录时系统自动记的。")
            }
        } else if memoriesError == nil {
            loadingText
        }
        if let memoriesError {
            Text(memoriesError)
                .font(.system(size: 12))
                .foregroundStyle(Theme.burn)
                .padding(.horizontal, 4)
        }
    }

    private func memoryRow(_ m: MemoryItem) -> some View {
        HStack(alignment: .top, spacing: 10) {
            VStack(alignment: .leading, spacing: 6) {
                Text(m.content)
                    .font(.system(size: 13))
                    .foregroundStyle(Theme.textPrimary)
                    .fixedSize(horizontal: false, vertical: true)
                HStack(spacing: 6) {
                    Text(kindLabel(m.kind))
                        .font(.system(size: 10, weight: .medium))
                        .foregroundStyle(kindColor(m.kind))
                        .padding(.horizontal, 7)
                        .padding(.vertical, 2)
                        .background(kindColor(m.kind).opacity(0.12), in: .capsule)
                    Text("\(monthDay(m.at)) 更新")
                        .font(.system(size: 11))
                        .foregroundStyle(Theme.textSecondary)
                }
            }
            Spacer()
            deleteButton(armed: memoryArmedID == m.id, disabled: memoryBusy) {
                removeMemory(m)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(Theme.card, in: .rect(cornerRadius: 14))
    }

    private func removeMemory(_ m: MemoryItem) {
        guard memoryArmedID == m.id else {
            arm(id: m.id, current: $memoryArmedID)
            return
        }
        memoryArmedID = nil
        memoryBusy = true
        memoriesError = nil
        Task {
            do {
                try await API.deleteMemory(id: m.id)
                deleteCount += 1
                await loadMemories()
            } catch {
                memoriesError = "删除失败:\(error.localizedDescription)"
            }
            memoryBusy = false
        }
    }

    private func loadMemories() async {
        memoriesError = nil
        do { memories = try await API.fetchMemories() } catch {
            memoriesError = "加载失败:\(error.localizedDescription)"
        }
    }

    private func kindLabel(_ kind: String) -> String {
        switch kind {
        case "alias": "叫法"
        case "habit": "习惯"
        case "correction": "纠正"
        default: kind
        }
    }

    private func kindColor(_ kind: String) -> Color {
        switch kind {
        case "alias": Theme.weight
        case "habit": Theme.intake
        case "correction": Theme.burn
        default: Theme.textSecondary
        }
    }

    // MARK: - 列表公用件

    /// 两击删:第一击浮出暖橙玻璃"确认"胶囊,3 秒不点自动缩回
    @ViewBuilder
    private func deleteButton(armed: Bool, disabled: Bool, action: @escaping () -> Void) -> some View {
        if armed {
            Button(action: action) {
                Text("确认")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 13)
                    .padding(.vertical, 7)
            }
            .glassEffect(.regular.tint(Theme.burn).interactive(), in: .capsule)
            .disabled(disabled)
            .transition(.scale(scale: 0.6).combined(with: .opacity))
        } else {
            Button(action: action) {
                Image(systemName: "trash")
                    .font(.system(size: 13))
                    .foregroundStyle(Theme.textSecondary.opacity(0.6))
                    .frame(width: 28, height: 28)
                    .contentShape(.rect)
            }
            .disabled(disabled)
        }
    }

    /// 第一击进入待确认态,3 秒没按第二击自动解除
    private func arm(id: Int, current: Binding<Int?>) {
        withAnimation(.spring(duration: 0.3)) { current.wrappedValue = id }
        Task {
            try? await Task.sleep(for: .seconds(3))
            if current.wrappedValue == id {
                withAnimation(.spring(duration: 0.3)) { current.wrappedValue = nil }
            }
        }
    }

    private func emptyCard(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 13))
            .foregroundStyle(Theme.textSecondary)
            .multilineTextAlignment(.center)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 24)
            .background(Theme.card, in: .rect(cornerRadius: 14))
    }

    private func hintText(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 11))
            .foregroundStyle(Theme.textSecondary.opacity(0.85))
            .padding(.horizontal, 4)
            .padding(.top, 2)
    }

    private var loadingText: some View {
        Text("加载中…")
            .font(.system(size: 13))
            .foregroundStyle(Theme.textSecondary.opacity(0.7))
            .frame(maxWidth: .infinity)
            .padding(.vertical, 20)
    }

    private func monthDay(_ d: Date) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "zh_CN")
        f.dateFormat = "M月d日"
        return f.string(from: d)
    }

    // MARK: - 行组件

    private func sectionHeader(_ title: String) -> some View {
        Text(title)
            .font(.system(size: 12, weight: .semibold))
            .foregroundStyle(Theme.textSecondary)
            .padding(.horizontal, 4)
            .padding(.top, 8)
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
                .frame(maxWidth: 160)
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

    private func readOnlyRow(label: String, value: String) -> some View {
        HStack {
            Text(label)
                .font(.system(size: 13))
                .foregroundStyle(Theme.textSecondary)
            Spacer()
            Text(value)
                .font(.system(size: 16, weight: .semibold, design: .rounded))
                .foregroundStyle(Theme.textSecondary)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 13)
        .background(Theme.card, in: .rect(cornerRadius: 14))
    }

    // 性别切换:选中态是一颗在两字之间液态滑动的玻璃胶囊
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

    @Namespace private var sexNS

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
                    .matchedGeometryEffect(id: "sex-thumb", in: sexNS)
            }
        }
    }

    // MARK: - 校验与保存

    private var trimmedNick: String {
        nickname.trimmingCharacters(in: .whitespaces)
    }

    private var valid: Bool {
        guard !trimmedNick.isEmpty, trimmedNick.count <= 50 else { return false }
        guard let h = Double(height), h > 0 else { return false }
        let thisYear = Calendar.current.component(.year, from: Date())
        guard let y = Int(birthYear), y >= 1900, y <= thisYear else { return false }
        return true
    }

    /// 只装改动了的字段(与 Web 同口径:逐项对比基线)
    private var patchBody: UserPatch {
        var p = UserPatch()
        if trimmedNick != baseline.nickname { p.nickname = trimmedNick }
        if let h = Double(height), h != baseline.heightCm { p.heightCm = h }
        if sex != baseline.sex { p.sex = sex }
        if let y = Int(birthYear), y != baseline.birthYear { p.birthYear = y }
        return p
    }

    private var changed: Bool { valid && !patchBody.isEmpty }

    private var saveButton: some View {
        Button {
            save()
        } label: {
            Text(busy ? "保存中…" : "保存档案")
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 13)
        }
        .glassEffect(.regular.tint(Theme.brand).interactive(), in: .capsule)
        .disabled(!changed || busy)
        .opacity(changed || busy ? 1 : 0.35)
        .animation(.easeOut(duration: 0.2), value: changed)
    }

    private func save() {
        guard changed, !busy else { return }
        focused = false
        busy = true
        error = nil
        let body = patchBody
        Task {
            do {
                try await API.patchUser(body)
                baseline = UserProfile(
                    id: baseline.id,
                    username: baseline.username,
                    nickname: trimmedNick,
                    heightCm: Double(height) ?? baseline.heightCm,
                    sex: sex,
                    birthYear: Int(birthYear) ?? baseline.birthYear
                )
                saveCount += 1
                showToast("档案已保存")
                await onSaved()
            } catch {
                self.error = error.localizedDescription
            }
            busy = false
        }
    }

    private func showToast(_ msg: String) {
        toast = msg
        Task {
            try? await Task.sleep(for: .seconds(3))
            if toast == msg { toast = nil }
        }
    }

    // MARK: - 退出登录

    @State private var loggingOut = false

    /// 退出登录:服务器删本枚令牌+清钥匙串,门卫切回登录页;数据都在云端不受影响
    private var logoutButton: some View {
        Button {
            guard !loggingOut else { return }
            loggingOut = true
            Task {
                await API.logout()
                onLogout()
            }
        } label: {
            Label(loggingOut ? "退出中…" : "退出登录", systemImage: "rectangle.portrait.and.arrow.right")
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(Theme.burn)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 13)
                .background(Theme.card, in: .rect(cornerRadius: 14))
        }
        .buttonStyle(PressableStyle())
        .disabled(loggingOut)
    }
}

#Preview {
    NavigationStack {
        SettingsView(
            profile: UserProfile(id: 1, username: "demo", nickname: "演示", heightCm: 175, sex: "male", birthYear: 1997),
            onSaved: {},
            onLogout: {}
        )
    }
}
