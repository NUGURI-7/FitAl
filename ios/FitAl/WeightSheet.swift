import Charts
import SwiftUI

// 体重面板(点体重卡弹起):近30天曲线(真实时间轴)+ 全部记录列表
// 记录可改(点数值改公斤数,时间戳不动)可删(两击确认);改删后曲线与主页联动刷新

struct WeightSheet: View {
    let weights: [WeightPoint]
    let onChanged: () -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var editingID: Int?
    @State private var editText = ""
    @State private var confirmingDeleteID: Int?
    @State private var busy = false
    @State private var errorMsg: String?

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                Text("体重 · 近30天")
                    .font(.system(size: 17, weight: .bold))
                    .foregroundStyle(Theme.textPrimary)
                    .padding(.top, 22)

                if weights.isEmpty {
                    Text("还没有体重记录,说一句\"今天72公斤\"就有了")
                        .font(.system(size: 13))
                        .foregroundStyle(Theme.textSecondary)
                        .padding(.vertical, 40)
                } else {
                    chart
                        .padding(.horizontal, 4)
                    recordList
                }

                if let errorMsg {
                    Text(errorMsg)
                        .font(.system(size: 12))
                        .foregroundStyle(Theme.burn)
                }
            }
            .padding(.horizontal, 20)
            .padding(.bottom, 16)
        }
        .presentationDetents([.large])
        .presentationDragIndicator(.visible)
        .presentationBackground(Theme.paper)
    }

    // MARK: - 曲线(官方图表框架,真实时间轴)

    private var chart: some View {
        Chart {
            ForEach(weights) { point in
                // 线下渐变填充:品牌绿淡淡晕开到透明
                AreaMark(
                    x: .value("时间", point.at),
                    yStart: .value("底", yDomain.lowerBound),
                    yEnd: .value("公斤", point.weightKg)
                )
                .foregroundStyle(
                    LinearGradient(
                        colors: [Theme.brand.opacity(0.22), Theme.brand.opacity(0)],
                        startPoint: .top, endPoint: .bottom
                    )
                )
                .interpolationMethod(.monotone)

                LineMark(
                    x: .value("时间", point.at),
                    y: .value("公斤", point.weightKg)
                )
                .foregroundStyle(Theme.brand)
                .lineStyle(StrokeStyle(lineWidth: 2.5, lineCap: .round))
                .interpolationMethod(.monotone)
            }

            // 只强调最新一个点
            if let last = weights.last {
                PointMark(
                    x: .value("时间", last.at),
                    y: .value("公斤", last.weightKg)
                )
                .foregroundStyle(Theme.brand)
                .symbolSize(70)
                .annotation(position: .top, spacing: 6) {
                    Text(last.weightKg.cleanString)
                        .font(.system(size: 11, weight: .bold, design: .rounded))
                        .foregroundStyle(Theme.brand)
                }
            }
        }
        .chartYScale(domain: yDomain)
        .chartXAxis {
            AxisMarks(values: .automatic(desiredCount: 4)) { _ in
                AxisValueLabel(format: .dateTime.month(.defaultDigits).day(),
                               centered: false)
                    .font(.system(size: 10))
                    .foregroundStyle(Theme.textSecondary.opacity(0.8))
            }
        }
        .chartYAxis {
            AxisMarks(position: .trailing, values: .automatic(desiredCount: 4)) { _ in
                AxisGridLine(stroke: StrokeStyle(lineWidth: 0.5, dash: [3, 3]))
                    .foregroundStyle(Theme.textSecondary.opacity(0.15))
                AxisValueLabel()
                    .font(.system(size: 10))
                    .foregroundStyle(Theme.textSecondary.opacity(0.8))
            }
        }
        .frame(height: 200)
        .padding(.top, 20)
        .padding([.horizontal, .bottom], 14)
        .background(Theme.card, in: .rect(cornerRadius: 18))
    }

    /// 纵轴上下各留 0.5kg 余量,免得曲线贴边
    private var yDomain: ClosedRange<Double> {
        let values = weights.map(\.weightKg)
        let lo = (values.min() ?? 0) - 0.5
        let hi = (values.max() ?? 100) + 0.5
        return lo...hi
    }

    // MARK: - 记录列表(点数值改,垃圾桶两击删)

    private var recordList: some View {
        VStack(spacing: 0) {
            HStack {
                Text("全部记录")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(Theme.textSecondary)
                Spacer()
            }
            .padding(.bottom, 4)

            ForEach(weights.reversed()) { point in
                recordRow(point)
                if point.id != weights.first?.id {
                    Divider().opacity(0.5)
                }
            }
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 12)
        .background(Theme.card, in: .rect(cornerRadius: 18))
    }

    private func recordRow(_ point: WeightPoint) -> some View {
        HStack(spacing: 10) {
            Text(rowDate(point.at))
                .font(.system(size: 13))
                .foregroundStyle(Theme.textSecondary)

            Spacer()

            if editingID == point.id {
                TextField("", text: $editText)
                    .keyboardType(.decimalPad)
                    .multilineTextAlignment(.trailing)
                    .font(.system(size: 15, weight: .semibold, design: .rounded))
                    .foregroundStyle(Theme.brand)
                    .frame(width: 64)
                Button {
                    saveEdit(point)
                } label: {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 20))
                        .foregroundStyle(Theme.brand)
                }
                .disabled(busy)
            } else {
                Button {
                    editingID = point.id
                    editText = point.weightKg.cleanString
                    confirmingDeleteID = nil
                } label: {
                    HStack(alignment: .firstTextBaseline, spacing: 2) {
                        Text(point.weightKg.cleanString)
                            .font(.system(size: 15, weight: .semibold, design: .rounded))
                            .foregroundStyle(Theme.textPrimary)
                        Text("kg")
                            .font(.system(size: 10))
                            .foregroundStyle(Theme.textSecondary)
                    }
                }
            }

            Button {
                if confirmingDeleteID == point.id {
                    performDelete(point)
                } else {
                    withAnimation(.spring(duration: 0.3)) { confirmingDeleteID = point.id }
                    Task {
                        try? await Task.sleep(for: .seconds(3))
                        if confirmingDeleteID == point.id {
                            withAnimation(.spring(duration: 0.3)) { confirmingDeleteID = nil }
                        }
                    }
                }
            } label: {
                Image(systemName: confirmingDeleteID == point.id ? "trash.fill" : "trash")
                    .font(.system(size: 14))
                    .foregroundStyle(confirmingDeleteID == point.id ? .white : Theme.textSecondary.opacity(0.6))
                    .frame(width: 30, height: 30)
                    .background(
                        confirmingDeleteID == point.id ? Color.red : .clear,
                        in: .circle
                    )
            }
            .disabled(busy)
        }
        .padding(.vertical, 8)
    }

    private func rowDate(_ d: Date) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "zh_CN")
        f.dateFormat = "M月d日 HH:mm"
        return f.string(from: d)
    }

    // MARK: - 改与删

    private func saveEdit(_ point: WeightPoint) {
        guard let v = Double(editText), v > 0 else {
            errorMsg = "体重数字不对劲:不能为空、零或负数"
            return
        }
        guard v != point.weightKg else {
            editingID = nil
            return
        }
        busy = true
        errorMsg = nil
        Task {
            do {
                try await API.patchRecord(
                    kind: "weight", id: point.id,
                    patch: RecordPatch(weightKg: v)
                )
                editingID = nil
                onChanged()
            } catch {
                errorMsg = "保存失败:\(error.localizedDescription)"
            }
            busy = false
        }
    }

    private func performDelete(_ point: WeightPoint) {
        busy = true
        errorMsg = nil
        Task {
            do {
                try await API.deleteRecord(kind: "weight", id: point.id)
                confirmingDeleteID = nil
                onChanged()
            } catch {
                errorMsg = "删除失败:\(error.localizedDescription)"
            }
            busy = false
        }
    }
}
