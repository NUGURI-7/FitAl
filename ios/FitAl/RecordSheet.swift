import SwiftUI

// 记录详情卡(底部弹起):展示 + 修改 + 删除
// 改克数/负重/次数/时长 → 后端按规矩重算热量;直接改热量 → 转"你报的"
// 删除两击确认,3 秒不点自动缩回;改/删成功后关卡,主页静默刷新

enum SelectedRecord: Identifiable {
    case food(FoodItem)
    case exercise(ExerciseItem)

    var id: String {
        switch self {
        case .food(let f): "food-\(f.id)"
        case .exercise(let e): "exercise-\(e.id)"
        }
    }
}

struct RecordSheet: View {
    let record: SelectedRecord
    let onChanged: () -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var confirmingDelete = false
    @State private var busy = false
    @State private var errorMsg: String?

    // 可编辑字段的文本态(空串=该记录没有这个字段,不显示)
    @State private var gramsText = ""
    @State private var loadText = ""
    @State private var repsText = ""
    @State private var durText = ""
    @State private var kcalText = ""
    private let original: (grams: String, load: String, reps: String, dur: String, kcal: String)

    init(record: SelectedRecord, onChanged: @escaping () -> Void) {
        self.record = record
        self.onChanged = onChanged
        var g = "", l = "", r = "", d = ""
        let k: String
        switch record {
        case .food(let f):
            if let v = f.grams { g = v.cleanString }
            k = f.kcal.cleanString
        case .exercise(let e):
            if let v = e.loadKg { l = v.cleanString }
            if let v = e.reps { r = "\(v)" }
            if let v = e.durationMin { d = String(format: "%.1f", v) }
            k = e.kcal.cleanString
        }
        original = (g, l, r, d, k)
        _gramsText = State(initialValue: g)
        _loadText = State(initialValue: l)
        _repsText = State(initialValue: r)
        _durText = State(initialValue: d)
        _kcalText = State(initialValue: k)
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 0) {
                header
                    .padding(.top, 22)
                    .padding(.bottom, 18)

                VStack(spacing: 0) {
                    editableRows
                    staticRows
                }
                .padding(.horizontal, 18)
                .background(Theme.card, in: .rect(cornerRadius: 18))

                if kcalText != original.kcal {
                    Text("直接改热量,会按你报的数记")
                        .font(.system(size: 11))
                        .foregroundStyle(Theme.textSecondary)
                        .padding(.top, 8)
                }

                if let errorMsg {
                    Text(errorMsg)
                        .font(.system(size: 12))
                        .foregroundStyle(Theme.burn)
                        .padding(.top, 10)
                }

                if dirty {
                    saveButton
                        .padding(.top, 16)
                }

                deleteButton
                    .padding(.top, dirty ? 10 : 24)
                    .padding(.bottom, 12)
            }
            .padding(.horizontal, 20)
        }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
        .presentationBackground(Theme.paper)
    }

    // MARK: - 头部

    private var header: some View {
        VStack(spacing: 6) {
            HStack(spacing: 6) {
                Image(systemName: icon)
                    .font(.system(size: 13, weight: .semibold))
                Text(title)
                    .font(.system(size: 18, weight: .bold))
            }
            .foregroundStyle(Theme.textPrimary)

            HStack(alignment: .firstTextBaseline, spacing: 3) {
                Text("\(Int(kcalValue.rounded()))")
                    .font(.system(size: 34, weight: .bold, design: .rounded))
                    .foregroundStyle(color)
                Text("千卡")
                    .font(.system(size: 12))
                    .foregroundStyle(Theme.textSecondary)
            }

            Text(sourceLabel)
                .font(.system(size: 11, weight: .medium))
                .foregroundStyle(Theme.textSecondary)
                .padding(.horizontal, 10)
                .padding(.vertical, 4)
                .background(Theme.textSecondary.opacity(0.08), in: .capsule)
        }
    }

    // MARK: - 可编辑行

    @ViewBuilder
    private var editableRows: some View {
        if case .food = record, !original.grams.isEmpty {
            editRow(label: "克数", text: $gramsText, unit: "克", keyboard: .decimalPad)
        }
        if case .exercise = record {
            if !original.load.isEmpty {
                editRow(label: "负重", text: $loadText, unit: "公斤", keyboard: .decimalPad)
            }
            if !original.reps.isEmpty {
                editRow(label: "次数", text: $repsText, unit: "次", keyboard: .numberPad)
            }
            if !original.dur.isEmpty {
                editRow(label: "时长", text: $durText, unit: "分钟", keyboard: .decimalPad)
            }
        }
        editRow(label: "热量", text: $kcalText, unit: "千卡", keyboard: .decimalPad)
    }

    private func editRow(
        label: String, text: Binding<String>, unit: String,
        keyboard: UIKeyboardType
    ) -> some View {
        VStack(spacing: 0) {
            HStack {
                Text(label)
                    .font(.system(size: 14))
                    .foregroundStyle(Theme.textSecondary)
                Spacer()
                TextField("", text: text)
                    .keyboardType(keyboard)
                    .multilineTextAlignment(.trailing)
                    .font(.system(size: 14, weight: .semibold, design: .rounded))
                    .foregroundStyle(Theme.brand)
                    .frame(maxWidth: 90)
                Text(unit)
                    .font(.system(size: 12))
                    .foregroundStyle(Theme.textSecondary)
            }
            .padding(.vertical, 10)
            Divider().opacity(0.5)
        }
    }

    // MARK: - 只读行

    @ViewBuilder
    private var staticRows: some View {
        let rows = staticRowData
        ForEach(rows, id: \.0) { label, value in
            HStack {
                Text(label)
                    .font(.system(size: 14))
                    .foregroundStyle(Theme.textSecondary)
                Spacer()
                Text(value)
                    .font(.system(size: 14, weight: .medium))
                    .foregroundStyle(Theme.textPrimary)
                    .multilineTextAlignment(.trailing)
            }
            .padding(.vertical, 10)
            if label != rows.last?.0 {
                Divider().opacity(0.5)
            }
        }
    }

    private var staticRowData: [(String, String)] {
        switch record {
        case .food(let f):
            var rows: [(String, String)] = []
            if let p = f.protein { rows.append(("蛋白质", String(format: "%.1f 克", p))) }
            if let v = f.fat { rows.append(("脂肪", String(format: "%.1f 克", v))) }
            if let v = f.cho { rows.append(("碳水", String(format: "%.1f 克", v))) }
            if let v = f.fiber { rows.append(("膳食纤维", String(format: "%.1f 克", v))) }
            if cleanFoodName(f.foodName) != f.foodName {
                rows.append(("成分表名", f.foodName))
            }
            return rows
        case .exercise(let e):
            var rows: [(String, String)] = []
            if let net = e.kcalNet { rows.append(("净耗", "\(Int(net.rounded())) 千卡")) }
            return rows
        }
    }

    // MARK: - 保存

    private var dirty: Bool {
        gramsText != original.grams || loadText != original.load
            || repsText != original.reps || durText != original.dur
            || kcalText != original.kcal
    }

    /// 校验改动字段:挡空/零/负/非数字
    private var patchIfValid: RecordPatch? {
        var p = RecordPatch()
        if gramsText != original.grams {
            guard let v = Double(gramsText), v > 0 else { return nil }
            p.grams = v
        }
        if loadText != original.load {
            guard let v = Double(loadText), v > 0 else { return nil }
            p.loadKg = v
        }
        if repsText != original.reps {
            guard let v = Int(repsText), v > 0 else { return nil }
            p.reps = v
        }
        if durText != original.dur {
            guard let v = Double(durText), v > 0 else { return nil }
            p.durationMin = v
        }
        if kcalText != original.kcal {
            guard let v = Double(kcalText), v > 0 else { return nil }
            p.kcal = v
        }
        return p
    }

    private var saveButton: some View {
        Button {
            guard let patch = patchIfValid else {
                errorMsg = "数字不对劲:不能为空、零或负数"
                return
            }
            busy = true
            errorMsg = nil
            Task {
                do {
                    try await API.patchRecord(kind: kind, id: recordID, patch: patch)
                    dismiss()
                    onChanged()
                } catch {
                    errorMsg = "保存失败:\(error.localizedDescription)"
                    busy = false
                }
            }
        } label: {
            Group {
                if busy {
                    ProgressView().tint(.white)
                } else {
                    Text("保存修改")
                        .font(.system(size: 15, weight: .semibold))
                }
            }
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(Theme.brand, in: .rect(cornerRadius: 16))
        }
        .disabled(busy)
    }

    // MARK: - 删除(两击确认)

    private var deleteButton: some View {
        Button {
            if confirmingDelete {
                performDelete()
            } else {
                withAnimation(.spring(duration: 0.3)) { confirmingDelete = true }
                Task {
                    try? await Task.sleep(for: .seconds(3))
                    withAnimation(.spring(duration: 0.3)) { confirmingDelete = false }
                }
            }
        } label: {
            HStack(spacing: 6) {
                if busy && confirmingDelete {
                    ProgressView().tint(.white)
                } else {
                    Image(systemName: "trash")
                        .font(.system(size: 14, weight: .semibold))
                    Text(confirmingDelete ? "再点一下确认删除" : "删除这条记录")
                        .font(.system(size: 15, weight: .semibold))
                }
            }
            .foregroundStyle(confirmingDelete ? .white : Color.red)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(
                confirmingDelete ? Color.red : Color.red.opacity(0.1),
                in: .rect(cornerRadius: 16)
            )
        }
        .disabled(busy)
    }

    private func performDelete() {
        busy = true
        errorMsg = nil
        Task {
            do {
                try await API.deleteRecord(kind: kind, id: recordID)
                dismiss()
                onChanged()
            } catch {
                errorMsg = "删除失败:\(error.localizedDescription)"
                busy = false
                confirmingDelete = false
            }
        }
    }

    // MARK: - 各字段按类型取值

    private var title: String {
        switch record {
        case .food(let f): cleanFoodName(f.foodName)
        case .exercise(let e): e.exerciseName
        }
    }

    private var icon: String {
        switch record {
        case .food: "fork.knife"
        case .exercise: "flame.fill"
        }
    }

    private var color: Color {
        switch record {
        case .food: Theme.intake
        case .exercise: Theme.burn
        }
    }

    private var kind: String {
        switch record {
        case .food: "food"
        case .exercise: "exercise"
        }
    }

    private var recordID: Int {
        switch record {
        case .food(let f): f.id
        case .exercise(let e): e.id
        }
    }

    private var kcalValue: Double {
        switch record {
        case .food(let f): f.kcal
        case .exercise(let e): e.kcal
        }
    }

    private var sourceLabel: String {
        let source = switch record {
        case .food(let f): f.source
        case .exercise(let e): e.source
        }
        return switch source {
        case "user_reported": "来源:你报的"
        case "user_food": "来源:自定义食物"
        case "food_table": "来源:成分表查表"
        case "met_table": "来源:MET 表计算"
        case "llm_estimated": "来源:AI 估算"
        default: "来源:\(source)"
        }
    }
}

// 展示辅助:去掉多余小数(60.0 → 60)
extension Double {
    var cleanString: String {
        truncatingRemainder(dividingBy: 1) == 0
            ? String(format: "%.0f", self)
            : String(format: "%.1f", self)
    }
}
