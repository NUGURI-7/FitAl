import Combine
import SwiftUI

// 第一屏(真数据):/days 日汇总 + /weights 曲线 + /chat 发送
// 口径与 Web 一致:净摄入=摄入−折算基础代谢−运动净耗,负值翻"净消耗";
// 今天的基础代谢按已过时间折算,每分钟本地自刷,不轮询服务器

struct HomeView: View {
    @State private var dayOffset = 0 // 0=今天,-1=昨天…
    @State private var day: APIDay?
    @State private var weights: [WeightPoint] = []
    @State private var loadFailed: String?

    @State private var appeared = false
    @State private var netDisplay: Double = 0
    @State private var netIsDeficit = false
    @State private var burnDisplay: Double = 0
    @State private var weightDisplay: Double = 0
    @State private var ringProgress: Double = 0

    @State private var inputText = ""
    @State private var sending = false
    @State private var toast: String?
    @State private var toastIsError = false
    @State private var sendCount = 0
    // 过程面板:一次发送一份状态事件流;seq 换值强制重挂,连发不串台
    @State private var procEvents: [ChatStatus] = []
    @State private var procDone = false
    @State private var procActive = false
    @State private var procSeq = 0
    // 回执压到面板收场后再弹,两者同位不打架
    @State private var pendingToast: (text: String, error: Bool)?
    @State private var expandedDishes: Set<String> = []
    @State private var armedDishID: String?
    @State private var dishDeleting = false
    @State private var selected: SelectedRecord?
    @State private var deleteCount = 0
    @State private var showWeightSheet = false
    @State private var showCalendar = false // 日历跳转:点顶栏日期直达任意历史日

    @State private var profile: UserProfile?
    @State private var menuOpen = false
    @State private var showSettings = false
    @Namespace private var menuGlassNS

    private let minuteTick = Timer.publish(every: 60, on: .main, in: .common).autoconnect()

    var body: some View {
        NavigationStack {
            Group {
                if day == nil, let msg = loadFailed {
                    errorState(msg)
                } else if day == nil {
                    ProgressView()
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    content
                }
            }
            .background(BreathingBackground())
            .overlay {
                // 菜单开着时点屏幕其他地方收起(与 Web 的全屏点击捕获层同责)
                if menuOpen {
                    Color.black.opacity(0.001)
                        .ignoresSafeArea()
                        .onTapGesture {
                            withAnimation(.spring(duration: 0.35)) { menuOpen = false }
                        }
                }
            }
            .safeAreaInset(edge: .bottom, spacing: 0) { inputBar }
            .navigationDestination(isPresented: $showSettings) {
                if let profile {
                    SettingsView(profile: profile) {
                        // 保存档案后:球上首字跟新,主页现算数字静默刷新
                        if let fresh = try? await API.fetchUser() { self.profile = fresh }
                        await load()
                    }
                }
            }
            .toolbar { dateToolbar }
            .toolbarTitleDisplayMode(.inline)
        }
        .sensoryFeedback(.success, trigger: sendCount)
        .sensoryFeedback(.impact, trigger: deleteCount)
        .sensoryFeedback(.impact(weight: .light), trigger: menuOpen)
        .sheet(item: $selected) { record in
            RecordSheet(record: record) {
                deleteCount += 1
                Task { await load() }
            }
        }
        .sheet(isPresented: $showWeightSheet) {
            WeightSheet(weights: weights) {
                deleteCount += 1
                Task { await load() }
            }
        }
        .sheet(isPresented: $showCalendar) { calendarSheet }
        .task(id: dayOffset) { await load() }
        .task { profile = try? await API.fetchUser() } // 头像球首字;失败不显示球,不打扰主链路
        .onReceive(minuteTick) { _ in
            if dayOffset == 0 { applyHero(animated: false) }
        }
    }

    // MARK: - 日期

    private var shownDate: Date {
        Calendar.current.date(byAdding: .day, value: dayOffset, to: Date()) ?? Date()
    }

    private var dateISO: String {
        // 必须显式带本地时区:ISO8601 格式化默认按 UTC 取日子,
        // 凌晨 0-8 点会把"今天"算成昨天,整条时间轴错位一天
        shownDate.formatted(Date.ISO8601FormatStyle(timeZone: .current).year().month().day())
    }

    private var dateTitle: String {
        switch dayOffset {
        case 0: "今天"
        case -1: "昨天"
        case -2: "前天"
        default: shownDate.formatted(.dateTime.month().day())
        }
    }

    private var dateSubtitle: String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "zh_CN")
        f.dateFormat = "M月d日 EEE"
        return f.string(from: shownDate)
    }

    /// 月历选择 → 换算成"距今天几天"(只许今天及以前;选完自动收起)
    private var calendarSelection: Binding<Date> {
        Binding(
            get: { shownDate },
            set: { picked in
                let cal = Calendar.current
                let days = cal.dateComponents(
                    [.day],
                    from: cal.startOfDay(for: Date()),
                    to: cal.startOfDay(for: picked)
                ).day ?? 0
                dayOffset = min(days, 0)
                showCalendar = false
            }
        )
    }

    private var calendarSheet: some View {
        VStack(spacing: 4) {
            DatePicker(
                "选择日期",
                selection: calendarSelection,
                in: ...Date(),
                displayedComponents: .date
            )
            .datePickerStyle(.graphical)
            .tint(Theme.brand)
            .environment(\.locale, Locale(identifier: "zh_CN"))

            if dayOffset != 0 {
                Button {
                    dayOffset = 0
                    showCalendar = false
                } label: {
                    Text("回到今天")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundStyle(Theme.brand)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                }
            }
        }
        .padding(.horizontal, 16)
        .padding(.top, 10)
        .presentationDetents([.medium])
        .presentationDragIndicator(.visible)
        .presentationBackground(Theme.paper)
    }

    @ToolbarContentBuilder
    private var dateToolbar: some ToolbarContent {
        ToolbarItem(placement: .topBarLeading) {
            Button {
                dayOffset -= 1
            } label: {
                Image(systemName: "chevron.left")
            }
        }
        ToolbarItem(placement: .principal) {
            // 点日期弹月历直达(2026-07-12 日历跳转),小箭头提示可点
            Button {
                showCalendar = true
            } label: {
                VStack(spacing: 0) {
                    HStack(spacing: 3) {
                        Text(dateTitle)
                            .font(.system(size: 16, weight: .bold))
                            .foregroundStyle(Theme.textPrimary)
                        Image(systemName: "chevron.down")
                            .font(.system(size: 9, weight: .bold))
                            .foregroundStyle(Theme.textSecondary)
                    }
                    Text(dateSubtitle)
                        .font(.system(size: 11))
                        .foregroundStyle(Theme.textSecondary)
                }
            }
            .buttonStyle(.plain)
        }
        ToolbarItem(placement: .topBarTrailing) {
            Button {
                dayOffset += 1
            } label: {
                Image(systemName: "chevron.right")
            }
            .disabled(dayOffset >= 0)
        }
    }

    // MARK: - 主内容

    private var content: some View {
        ScrollView {
            VStack(spacing: 14) {
                statRow
                    .entrance(appeared, index: 0)
                if let day {
                    if day.meals.isEmpty && day.sessions.isEmpty {
                        emptyCard
                            .entrance(appeared, index: 1)
                    } else {
                        if !day.meals.isEmpty {
                            dietCard(day)
                                .entrance(appeared, index: 1)
                                .scrollBreathing()
                        }
                        if !day.sessions.isEmpty {
                            exerciseCard(day)
                                .entrance(appeared, index: 2)
                                .scrollBreathing()
                        }
                        Text("点明细可改可删 · 菜行可展开成分")
                            .font(.system(size: 11))
                            .foregroundStyle(Theme.textSecondary.opacity(0.7))
                            .padding(.top, 2)
                            .entrance(appeared, index: 3)
                    }
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 10)
            .padding(.bottom, 16)
        }
    }

    private var emptyCard: some View {
        VStack(spacing: 10) {
            Image(systemName: "leaf")
                .font(.system(size: 26))
                .foregroundStyle(Theme.brand.opacity(0.5))
            Text(dayOffset == 0 ? "今天还没有记录" : "这一天没有记录")
                .font(.system(size: 15, weight: .medium))
                .foregroundStyle(Theme.textPrimary)
            if dayOffset == 0 {
                Text("在下面说一句就好,比如:吃了一个苹果")
                    .font(.system(size: 12))
                    .foregroundStyle(Theme.textSecondary)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 44)
        .background(Theme.card, in: .rect(cornerRadius: 24))
        .shadow(color: .black.opacity(0.04), radius: 12, y: 4)
    }

    private func errorState(_ msg: String) -> some View {
        VStack(spacing: 12) {
            Image(systemName: "wifi.exclamationmark")
                .font(.system(size: 30))
                .foregroundStyle(Theme.textSecondary)
            Text("连不上服务器")
                .font(.system(size: 16, weight: .semibold))
                .foregroundStyle(Theme.textPrimary)
            Text(msg)
                .font(.system(size: 12))
                .foregroundStyle(Theme.textSecondary)
                .multilineTextAlignment(.center)
            Button {
                Task { await load() }
            } label: {
                Text("重试")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 26)
                    .padding(.vertical, 10)
            }
            .glassEffect(.regular.tint(Theme.brand).interactive(), in: .capsule)
            .padding(.top, 6)
        }
        .padding(.horizontal, 30)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - 三枚指标卡(净摄入 / 消耗 / 体重)

    private var statRow: some View {
        HStack(spacing: 10) {
            statTile(
                title: netIsDeficit ? "净消耗" : "净摄入",
                color: netIsDeficit ? Theme.burn : Theme.intake,
                number: Text("\(Int(netDisplay.rounded()))"),
                numberValue: netDisplay,
                unit: "千卡", sub: "", gradientNumber: true
            ) { EmptyView() }

            statTile(
                title: "消耗", color: Theme.burn,
                number: Text("\(Int(burnDisplay.rounded()))"),
                numberValue: burnDisplay,
                unit: "千卡", sub: "基础代谢+运动"
            ) {
                ProgressRing(progress: ringProgress, color: Theme.burn)
                    .frame(width: 22, height: 22)
                    .padding(10)
            }

            Button {
                showWeightSheet = true
            } label: {
                statTile(
                    title: "体重", color: Theme.weight,
                    number: Text(weightDisplay > 0 ? String(format: "%.1f", weightDisplay) : "–"),
                    numberValue: weightDisplay,
                    unit: "kg", sub: weightSub
                ) {
                    if weights.count >= 2 {
                        Sparkline(values: weights.map(\.weightKg), color: Theme.weight)
                            .frame(width: 44, height: 16)
                            .padding(.trailing, 10)
                            .padding(.top, 12)
                    }
                }
            }
            .buttonStyle(PressableStyle())
        }
    }

    private var weightSub: String {
        guard let day else { return "" }
        let todayKg = day.weight
        let dayStart = Calendar.current.startOfDay(for: shownDate)
        let prev = weights.last(where: { $0.at < dayStart })
        if let todayKg, let prev {
            let delta = todayKg - prev.weightKg
            return String(format: "%+.1f 较上次", delta)
        }
        if let prev, todayKg == nil {
            let f = DateFormatter()
            f.locale = Locale(identifier: "zh_CN")
            f.dateFormat = "M/d"
            return "上次 \(f.string(from: prev.at))"
        }
        return ""
    }

    private func statTile(
        title: String, color: Color,
        number: Text, numberValue: Double,
        unit: String, sub: String, gradientNumber: Bool = false,
        @ViewBuilder accessory: () -> some View
    ) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title)
                .font(.system(size: 11, weight: .medium))
                .foregroundStyle(color)

            HStack(alignment: .firstTextBaseline, spacing: 2) {
                number
                    .font(.system(size: 22, weight: .bold, design: .rounded))
                    .foregroundStyle(
                        gradientNumber
                            ? AnyShapeStyle(
                                LinearGradient(
                                    colors: [color, color.opacity(0.55)],
                                    startPoint: .top, endPoint: .bottom
                                )
                            )
                            : AnyShapeStyle(Theme.textPrimary)
                    )
                    .contentTransition(.numericText(value: numberValue))
                    .monospacedDigit()
                Text(unit)
                    .font(.system(size: 10))
                    .foregroundStyle(Theme.textSecondary)
            }

            Text(sub.isEmpty ? " " : sub)
                .font(.system(size: 9))
                .foregroundStyle(Theme.textSecondary.opacity(0.8))
                .lineLimit(1)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .background(alignment: .topTrailing) {
            RadialGradient(
                colors: [color.opacity(0.18), color.opacity(0)],
                center: .center, startRadius: 0, endRadius: 42
            )
            .frame(width: 84, height: 84)
            .offset(x: 24, y: -24)
        }
        .overlay(alignment: .topTrailing) { accessory() }
        .background(Theme.card)
        .clipShape(.rect(cornerRadius: 18))
        .shadow(color: .black.opacity(0.04), radius: 10, y: 3)
    }

    // MARK: - 饮食卡

    private func dietCard(_ day: APIDay) -> some View {
        sectionCard(
            title: "饮食", icon: "fork.knife", color: Theme.intake,
            totalKcal: Int(day.intakeKcal.rounded())
        ) {
            ForEach(day.meals) { meal in
                VStack(spacing: 0) {
                    groupHeader(name: meal.name ?? "一顿饭", count: mealRecordCount(meal), kcal: meal.kcalTotal)
                    ForEach(meal.items) { entry in
                        switch entry {
                        case .food(let f):
                            itemRow(
                                name: cleanFoodName(f.foodName),
                                detail: foodDetail(f),
                                kcal: Int(f.kcal.rounded()),
                                color: Theme.intake
                            ) { selected = .food(f) }
                        case .dish(let d):
                            dishRows(d, entryID: entry.id)
                        }
                    }
                }
            }
        }
    }

    /// 菜行:点击展开/收起成分清单(成分缩进,弹簧过渡);行尾垃圾桶两击删整菜
    @ViewBuilder
    private func dishRows(_ d: Dish, entryID: String) -> some View {
        let expanded = expandedDishes.contains(entryID)

        HStack(spacing: 6) {
            Button {
                withAnimation(.spring(duration: 0.45)) {
                    if expanded {
                        expandedDishes.remove(entryID)
                    } else {
                        expandedDishes.insert(entryID)
                    }
                }
            } label: {
                HStack {
                    Circle()
                        .fill(Theme.intake.opacity(0.5))
                        .frame(width: 5, height: 5)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(d.dishName)
                            .font(.system(size: 15, weight: .medium))
                            .foregroundStyle(Theme.textPrimary)
                        Text("\(Int(d.totalGrams.rounded())) 克 · \(d.items.count) 成分")
                            .font(.system(size: 12))
                            .foregroundStyle(Theme.textSecondary)
                    }
                    Spacer()
                    Text("\(Int(d.kcalTotal.rounded()))")
                        .font(.system(size: 15, weight: .semibold, design: .rounded))
                        .foregroundStyle(Theme.textPrimary)
                    Image(systemName: "chevron.down")
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundStyle(Theme.textSecondary.opacity(0.6))
                        .rotationEffect(.degrees(expanded ? 180 : 0))
                }
                .contentShape(.rect)
            }
            .buttonStyle(PressableStyle())

            dishDeleteButton(d, entryID: entryID)
        }
        .padding(.vertical, 8)

        if expanded {
            VStack(spacing: 0) {
                ForEach(d.items) { f in
                    Button {
                        selected = .food(f)
                    } label: {
                        HStack {
                            RoundedRectangle(cornerRadius: 1)
                                .fill(Theme.intake.opacity(0.25))
                                .frame(width: 2, height: 26)
                            VStack(alignment: .leading, spacing: 1) {
                                Text(cleanFoodName(f.foodName))
                                    .font(.system(size: 13, weight: .medium))
                                    .foregroundStyle(Theme.textPrimary.opacity(0.85))
                                Text(foodDetail(f))
                                    .font(.system(size: 11))
                                    .foregroundStyle(Theme.textSecondary)
                            }
                            Spacer()
                            Text("\(Int(f.kcal.rounded()))")
                                .font(.system(size: 13, weight: .semibold, design: .rounded))
                                .foregroundStyle(Theme.textSecondary)
                        }
                        .padding(.vertical, 5)
                        .padding(.leading, 14)
                        .contentShape(.rect)
                    }
                    .buttonStyle(PressableStyle())
                }
            }
            .transition(.opacity.combined(with: .move(edge: .top)))
        }
    }

    /// 菜行整删:两击确认(第一击浮出暖橙玻璃"确认"胶囊,3 秒缩回,与设置页同族)
    @ViewBuilder
    private func dishDeleteButton(_ d: Dish, entryID: String) -> some View {
        if armedDishID == entryID {
            Button {
                deleteDish(d)
            } label: {
                Text("确认")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 6)
            }
            .glassEffect(.regular.tint(Theme.burn).interactive(), in: .capsule)
            .disabled(dishDeleting)
            .transition(.scale(scale: 0.6).combined(with: .opacity))
        } else {
            Button {
                withAnimation(.spring(duration: 0.3)) { armedDishID = entryID }
                Task {
                    try? await Task.sleep(for: .seconds(3))
                    if armedDishID == entryID {
                        withAnimation(.spring(duration: 0.3)) { armedDishID = nil }
                    }
                }
            } label: {
                Image(systemName: "trash")
                    .font(.system(size: 12))
                    .foregroundStyle(Theme.textSecondary.opacity(0.5))
                    .frame(width: 26, height: 26)
                    .contentShape(.rect)
            }
            .disabled(dishDeleting)
        }
    }

    /// 菜不是实体,整删=逐条删成分(raw 唯一事实源),所在顿由后端增量重算
    private func deleteDish(_ d: Dish) {
        armedDishID = nil
        dishDeleting = true
        Task {
            do {
                for item in d.items {
                    try await API.deleteRecord(kind: "food", id: item.id)
                }
                deleteCount += 1
                showToast("已删除整道「\(d.dishName)」")
            } catch {
                showToast("删除失败:\(error.localizedDescription)", error: true)
            }
            await load()
            dishDeleting = false
        }
    }

    private func foodDetail(_ f: FoodItem) -> String {
        var parts: [String] = []
        if let g = f.grams { parts.append("\(Int(g.rounded())) 克") }
        if let tag = sourceTag(f.source) { parts.append(tag) }
        return parts.isEmpty ? "—" : parts.joined(separator: " · ")
    }

    /// "条"数按 raw 记录计:菜按其成分数计,不把菜自身算一条(与 Web 同口径)
    private func mealRecordCount(_ meal: APIGroup<MealEntry>) -> Int {
        meal.items.reduce(0) { n, e in
            switch e {
            case .food: n + 1
            case .dish(let d): n + d.items.count
            }
        }
    }

    // MARK: - 运动卡

    private func exerciseCard(_ day: APIDay) -> some View {
        sectionCard(
            title: "运动", icon: "flame.fill", color: Theme.burn,
            totalKcal: Int(day.burnKcal.rounded())
        ) {
            ForEach(day.sessions) { session in
                VStack(spacing: 0) {
                    groupHeader(name: session.name ?? "一场训练", count: session.items.count, kcal: session.kcalTotal)
                    ForEach(session.items) { item in
                        itemRow(
                            name: item.exerciseName,
                            detail: exerciseDetail(item),
                            kcal: Int(item.kcal.rounded()),
                            color: Theme.burn
                        ) { selected = .exercise(item) }
                    }
                }
            }
        }
    }

    private func exerciseDetail(_ e: ExerciseItem) -> String {
        var parts: [String] = []
        if let load = e.loadKg, let reps = e.reps {
            parts.append("\(load.cleanString)kg × \(reps)")
        } else if let reps = e.reps {
            parts.append("× \(reps) 次")
        }
        if let dur = e.durationMin {
            parts.append("\(String(format: "%.1f", dur)) 分钟")
        }
        if let tag = sourceTag(e.source) { parts.append(tag) }
        return parts.isEmpty ? "—" : parts.joined(separator: " · ")
    }

    private func sourceTag(_ source: String) -> String? {
        switch source {
        case "llm_estimated": "估算"
        case "user_reported": "你报的"
        case "user_food": "自定义"
        default: nil
        }
    }

    // MARK: - 通用卡片与行

    private func groupHeader(name: String, count: Int, kcal: Double) -> some View {
        HStack(alignment: .firstTextBaseline) {
            Text(name)
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(Theme.textSecondary)
            Text("\(count) 条")
                .font(.system(size: 11))
                .foregroundStyle(Theme.textSecondary.opacity(0.7))
            Spacer()
            Text("\(Int(kcal.rounded())) 千卡")
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(Theme.textSecondary)
        }
        .padding(.top, 14)
        .padding(.bottom, 6)
    }

    private func sectionCard(
        title: String, icon: String, color: Color, totalKcal: Int,
        @ViewBuilder content: () -> some View
    ) -> some View {
        VStack(spacing: 0) {
            HStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(.white)
                    .frame(width: 30, height: 30)
                    .background(
                        LinearGradient(
                            colors: [color.opacity(0.85), color],
                            startPoint: .topLeading, endPoint: .bottomTrailing
                        ),
                        in: .circle
                    )
                Text(title)
                    .font(.system(size: 17, weight: .bold))
                    .foregroundStyle(Theme.textPrimary)
                Spacer()
                Text("\(totalKcal)")
                    .font(.system(size: 17, weight: .bold, design: .rounded))
                    .foregroundStyle(color)
                Text("千卡")
                    .font(.system(size: 12))
                    .foregroundStyle(Theme.textSecondary)
            }
            content()
        }
        .padding(18)
        .background(Theme.card, in: .rect(cornerRadius: 24))
        .shadow(color: .black.opacity(0.04), radius: 12, y: 4)
    }

    private func itemRow(
        name: String, detail: String, kcal: Int, color: Color,
        onTap: @escaping () -> Void = {}
    ) -> some View {
        Button(action: onTap) {
            HStack {
                Circle()
                    .fill(color.opacity(0.5))
                    .frame(width: 5, height: 5)
                VStack(alignment: .leading, spacing: 2) {
                    Text(name)
                        .font(.system(size: 15, weight: .medium))
                        .foregroundStyle(Theme.textPrimary)
                    Text(detail)
                        .font(.system(size: 12))
                        .foregroundStyle(Theme.textSecondary)
                }
                Spacer()
                Text("\(kcal)")
                    .font(.system(size: 15, weight: .semibold, design: .rounded))
                    .foregroundStyle(Theme.textPrimary)
            }
            .padding(.vertical, 8)
            .contentShape(.rect)
        }
        .buttonStyle(PressableStyle())
    }

    // MARK: - 底部输入条 + 回执气泡

    private var inputBar: some View {
        VStack(spacing: 8) {
            // 发送后的过程面板:节点逐个点亮,走完收起让位回执
            if procActive {
                ProcessPanel(events: procEvents, done: procDone) {
                    procActive = false
                    if let p = pendingToast {
                        showToast(p.text, error: p.error)
                        pendingToast = nil
                    }
                }
                .id(procSeq)
                .transition(.move(edge: .bottom).combined(with: .opacity))
            }

            if let toast {
                Text(toast)
                    .font(.system(size: 13))
                    .foregroundStyle(toastIsError ? .white : Theme.textPrimary)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                    .glassEffect(toastIsError ? .regular.tint(Theme.burn) : .regular)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
            }

            // 头像球悬浮菜单:输入条上方靠左,照搬 Web(点球浮出齿轮,点齿轮进设置页)
            if profile != nil {
                HStack {
                    menuCluster
                    Spacer()
                }
            }

            GlassEffectContainer(spacing: 12) {
                HStack(spacing: 12) {
                    TextField("说一句,记一笔", text: $inputText)
                        .font(.system(size: 15))
                        .padding(.horizontal, 18)
                        .padding(.vertical, 12)
                        .glassEffect()
                        .onSubmit { send() }

                    SendButton(sending: sending) { send() }
                }
            }
        }
        .padding(.horizontal, 16)
        .padding(.top, 8)
        .padding(.bottom, 6)
        .animation(.spring(duration: 0.4), value: toast)
        .animation(.spring(duration: 0.4), value: procActive)
    }

    // MARK: - 头像球菜单(液态玻璃,齿轮从球里长出来;后续新功能继续往上摞球)

    private var avatarInitial: String {
        let first = profile?.nickname.trimmingCharacters(in: .whitespaces).first
        return first.map(String.init) ?? "我"
    }

    private var menuCluster: some View {
        GlassEffectContainer(spacing: 16) {
            VStack(spacing: 10) {
                if menuOpen {
                    Button {
                        withAnimation(.spring(duration: 0.35)) { menuOpen = false }
                        showSettings = true
                    } label: {
                        Image(systemName: "gearshape.fill")
                            .font(.system(size: 16, weight: .semibold))
                            .foregroundStyle(Theme.textPrimary)
                            .frame(width: 40, height: 40)
                    }
                    .glassEffect(.regular.interactive(), in: .circle)
                    .glassEffectID("menu-gear", in: menuGlassNS)
                }

                Button {
                    withAnimation(.spring(duration: 0.4)) { menuOpen.toggle() }
                } label: {
                    Text(avatarInitial)
                        .font(.system(size: 17, weight: .bold))
                        .foregroundStyle(Theme.textPrimary)
                        .frame(width: 44, height: 44)
                }
                .glassEffect(.regular.interactive(), in: .circle)
                .glassEffectID("menu-avatar", in: menuGlassNS)
            }
        }
    }

    // MARK: - 数据加载与口径计算

    private func load() async {
        loadFailed = nil
        do {
            async let d = API.fetchDay(dateISO)
            async let w = API.fetchWeights()
            let (dayData, weightData) = try await (d, w)
            day = dayData
            weights = weightData
            if !appeared { appeared = true }
            applyHero(animated: true)
        } catch {
            // 静默刷新原则:已有数据时失败不清屏,仅首屏失败进错误态
            if day == nil {
                loadFailed = error.localizedDescription
            }
        }
    }

    /// 英雄区口径(与 Web Hero 完全一致)
    private func applyHero(animated: Bool) {
        guard let day else { return }
        var net: Double? = nil
        var burnTotal: Double? = nil
        if let bmr = day.bmrKcal {
            let frac: Double
            if dayOffset == 0 {
                let start = Calendar.current.startOfDay(for: Date())
                frac = min(1, Date().timeIntervalSince(start) / 86_400)
            } else {
                frac = 1
            }
            burnTotal = bmr * frac + day.burnNetKcal
            net = day.intakeKcal - burnTotal!
        }

        let apply = {
            netIsDeficit = (net ?? 0) < 0
            netDisplay = abs(net ?? 0)
            burnDisplay = burnTotal ?? 0
            weightDisplay = day.weight
                ?? weights.last(where: { $0.at < Calendar.current.startOfDay(for: shownDate) })?.weightKg
                ?? 0
            if let bmr = day.bmrKcal, bmr > 0, let burnTotal {
                ringProgress = min(1, burnTotal / bmr)
            } else {
                ringProgress = 0
            }
        }
        if animated {
            withAnimation(.spring(duration: 1.2)) { apply() }
        } else {
            apply()
        }
    }

    // MARK: - 发送

    private func send() {
        let text = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !sending else { return }
        sending = true
        inputText = ""
        toast = nil // 旧气泡先退场,发送期间舞台交给过程面板
        // 上一条回执还压着没弹(面板收场中就连发)则先弹出来
        if let p = pendingToast {
            showToast(p.text, error: p.error)
            pendingToast = nil
        }
        procSeq += 1
        procEvents = []
        procDone = false
        procActive = true
        Task {
            do {
                let reply = try await API.sendChat(text) { s in
                    Task { @MainActor in procEvents.append(s) }
                }
                sendCount += 1
                pendingToast = (reply, false)
                if dayOffset != 0 { dayOffset = 0 } // 记录永远落在"现在",发送后跳回今天
                await load()
            } catch {
                pendingToast = ("发送失败:\(error.localizedDescription)", true)
                inputText = text // 失败还回输入,方便重发
            }
            procDone = true
            sending = false
        }
    }

    private func showToast(_ msg: String, error: Bool = false) {
        toast = msg
        toastIsError = error
        Task {
            try? await Task.sleep(for: .seconds(4))
            if toast == msg { toast = nil }
        }
    }
}

// MARK: - 会呼吸的背景:纸感底上两团极淡色晕缓慢漂移

private struct BreathingBackground: View {
    var body: some View {
        ZStack {
            Theme.paper
            // 柔光用径向渐变,静态:常驻循环动画费电占 GPU,业界不这么干(2026-07-09 用户砍定)
            softGlow(Theme.brand.opacity(0.09), size: 380)
                .offset(x: -85, y: -120)
            softGlow(Theme.burn.opacity(0.07), size: 340)
                .offset(x: 110, y: 295)
        }
        .ignoresSafeArea()
    }

    private func softGlow(_ color: Color, size: CGFloat) -> some View {
        RadialGradient(
            colors: [color, color.opacity(0)],
            center: .center, startRadius: 0, endRadius: size / 2
        )
        .frame(width: size, height: size)
    }
}

// MARK: - 细进度环(消耗卡)

private struct ProgressRing: View {
    let progress: Double
    let color: Color

    var body: some View {
        ZStack {
            Circle()
                .stroke(color.opacity(0.15), lineWidth: 3)
            Circle()
                .trim(from: 0, to: progress)
                .stroke(color, style: StrokeStyle(lineWidth: 3, lineCap: .round))
                .rotationEffect(.degrees(-90))
        }
    }
}

// MARK: - 迷你趋势线(体重卡)

private struct Sparkline: View {
    let values: [Double]
    let color: Color

    var body: some View {
        GeometryReader { geo in
            let minV = values.min() ?? 0
            let maxV = values.max() ?? 1
            let span = max(maxV - minV, 0.001)
            let stepX = geo.size.width / CGFloat(max(values.count - 1, 1))
            let points = values.enumerated().map { i, v in
                CGPoint(
                    x: CGFloat(i) * stepX,
                    y: geo.size.height * (1 - CGFloat((v - minV) / span))
                )
            }

            ZStack {
                Path { p in
                    guard let first = points.first else { return }
                    p.move(to: first)
                    for pt in points.dropFirst() { p.addLine(to: pt) }
                }
                .stroke(
                    color.opacity(0.8),
                    style: StrokeStyle(lineWidth: 1.5, lineCap: .round, lineJoin: .round)
                )

                if let last = points.last {
                    Circle()
                        .fill(color)
                        .frame(width: 4, height: 4)
                        .position(last)
                }
            }
        }
    }
}

// MARK: - 发送按钮:待机呼吸微光,按下爆光,发送中转圈

private struct SendButton: View {
    let sending: Bool
    let action: () -> Void
    @State private var bursting = false

    var body: some View {
        Button {
            guard !sending else { return }
            bursting = true
            action()
            Task {
                try? await Task.sleep(for: .milliseconds(350))
                bursting = false
            }
        } label: {
            Group {
                if sending {
                    ProgressView()
                        .tint(.white)
                } else {
                    Image(systemName: "arrow.up")
                        .font(.system(size: 16, weight: .bold))
                }
            }
            .foregroundStyle(.white)
            .frame(width: 44, height: 44)
        }
        .glassEffect(.regular.tint(Theme.brand).interactive(), in: .circle)
        .background {
            // 静态微光;仅按下发送时爆光一瞬(响应式动效,不做常驻循环)
            RadialGradient(
                colors: [
                    Theme.brand.opacity(bursting ? 0.5 : 0.16),
                    Theme.brand.opacity(0),
                ],
                center: .center, startRadius: 8, endRadius: 34
            )
            .frame(width: 68, height: 68)
            .scaleEffect(bursting ? 1.5 : 1.0)
            .animation(.spring(duration: 0.35), value: bursting)
        }
        .scaleEffect(bursting ? 1.08 : 1)
        .animation(.spring(duration: 0.3), value: bursting)
    }
}

// MARK: - 入场与滚动动效

// 卡片依次浮现:雾里显形(模糊+缩放+上浮)
private extension View {
    func entrance(_ appeared: Bool, index: Int) -> some View {
        self
            .opacity(appeared ? 1 : 0)
            .blur(radius: appeared ? 0 : 6)
            .scaleEffect(appeared ? 1 : 0.97)
            .offset(y: appeared ? 0 : 18)
            .animation(.spring(duration: 0.65).delay(Double(index) * 0.09), value: appeared)
    }

    // 滚动进出屏幕边缘时轻微缩放呼吸
    func scrollBreathing() -> some View {
        scrollTransition(.interactive) { content, phase in
            content
                .scaleEffect(phase.isIdentity ? 1 : 0.96)
                .opacity(phase.isIdentity ? 1 : 0.75)
        }
    }
}

#Preview {
    HomeView()
}
