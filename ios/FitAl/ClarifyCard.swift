import SwiftUI

// 澄清小表单(契约 event:clarify,2026-07-12):罕见兜底——运动段缺数
// 连估都估不出时浮出;问题固定=一句问话+数字输入框+单位,不做通用表单。
// 表单易失(收起/杀 app 都无所谓):数据躺在服务器的待补行上,不丢。

struct ClarifyCard: View {
    let clarify: ChatClarify
    /// 补交成功:带回执文字,父层弹气泡+刷新
    var onDone: (String) -> Void
    /// 收起(先不填):数据不丢,待补段躺在服务器上
    var onDismiss: () -> Void
    /// 已补过/不在待补态(409):父层收起并提示
    var onStale: (String) -> Void

    @State private var values: [String: String] = [:]
    @State private var submitting = false
    @State private var errorMsg: String?

    /// 只提交填了正数的格子;后端重跑同套校验,没填够会打回
    private var answers: [String: Double] {
        var out: [String: Double] = [:]
        for q in clarify.questions {
            if let v = Double(values[q.key] ?? ""), v > 0 { out[q.key] = v }
        }
        return out
    }

    private var ready: Bool {
        answers.count >= clarify.minAnswers
            && clarify.questions.allSatisfy { !$0.required || answers[$0.key] != nil }
    }

    private var eitherOne: Bool {
        clarify.minAnswers == 1 && clarify.questions.count > 1
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .top, spacing: 8) {
                Image(systemName: "questionmark.circle.fill")
                    .font(.system(size: 17))
                    .foregroundStyle(Theme.brand)
                VStack(alignment: .leading, spacing: 2) {
                    Text("还差个数才能记上")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundStyle(Theme.textPrimary)
                    Text("「\(clarify.text)」")
                        .font(.system(size: 12))
                        .foregroundStyle(Theme.textSecondary)
                        .lineLimit(1)
                }
                Spacer(minLength: 0)
                Button(action: onDismiss) {
                    Image(systemName: "xmark")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundStyle(Theme.textSecondary)
                        .frame(width: 26, height: 26)
                        .contentShape(.circle)
                }
                .buttonStyle(PressableStyle())
            }

            ForEach(clarify.questions, id: \.key) { q in
                HStack(spacing: 8) {
                    Text(q.prompt)
                        .font(.system(size: 13))
                        .foregroundStyle(Theme.textPrimary)
                        .lineLimit(1)
                    Spacer(minLength: 8)
                    TextField("", text: binding(q.key))
                        .keyboardType(.decimalPad)
                        .multilineTextAlignment(.trailing)
                        .font(.system(size: 15, weight: .semibold, design: .rounded))
                        .frame(width: 68)
                        .padding(.vertical, 7)
                        .padding(.horizontal, 10)
                        .background(
                            // 玻璃卡上白底会被冲淡(用户真机反馈):描边+投影提可见度
                            RoundedRectangle(cornerRadius: 10)
                                .fill(Theme.card)
                                .shadow(color: .black.opacity(0.10), radius: 3, y: 1)
                        )
                        .overlay(
                            RoundedRectangle(cornerRadius: 10)
                                .stroke(Color.black.opacity(0.14), lineWidth: 1)
                        )
                        .disabled(submitting)
                    Text(q.unit)
                        .font(.system(size: 12))
                        .foregroundStyle(Theme.textSecondary)
                        .frame(width: 30, alignment: .leading)
                }
            }

            if eitherOne {
                Text("填其中一项即可")
                    .font(.system(size: 11))
                    .foregroundStyle(Theme.textSecondary)
            }
            if let errorMsg {
                Text(errorMsg)
                    .font(.system(size: 12))
                    .foregroundStyle(Theme.burn)
            }

            Button(action: submit) {
                Text(submitting ? "记录中…" : "补交记上")
                    .font(.system(size: 14, weight: .bold))
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 11)
            }
            .glassEffect(.regular.tint(Theme.brand).interactive(), in: .capsule)
            .disabled(!ready || submitting)
            .opacity(ready ? 1 : 0.4)
        }
        .padding(16)
        .glassEffect(.regular, in: .rect(cornerRadius: 22))
    }

    private func binding(_ key: String) -> Binding<String> {
        Binding(get: { values[key] ?? "" }, set: { values[key] = $0 })
    }

    private func submit() {
        guard ready, !submitting else { return }
        submitting = true
        errorMsg = nil
        let payload = answers
        Task {
            do {
                let reply = try await API.submitClarify(
                    inputId: clarify.inputId, answers: payload
                )
                onDone(reply)
            } catch {
                let msg = error.localizedDescription
                if msg.contains("待补") {
                    onStale(msg) // 409:这行已经补过,表单没有存在意义
                } else {
                    errorMsg = msg
                    submitting = false
                }
            }
        }
    }
}
