import SwiftUI

// 发送后的液态玻璃过程面板:流程节点(理解→按实际路数的饮食/运动/记住→入库)
// 随后端状态事件逐个点亮,走完收起让位记录卡片与回执。
// 展示节奏与事件到达解耦:事件只决定能不能往前走,每步保底亮一小会儿,
// 快句子(纯体重一秒多)不闪跳;流结束后积压事件快进消化。
struct ProcessPanel: View {
    let events: [ChatStatus]
    let done: Bool // 流已结束(拿到回执或请求失败)
    let onGone: () -> Void // 收场动画播完,可以卸载了

    @State private var applied = 0 // 已应用到画面的事件数
    @State private var closing = false
    @State private var lastStep = Date.distantPast

    private static let minStep: TimeInterval = 0.45
    private static let fastStep: TimeInterval = 0.16 // 流已结束时快进积压事件
    private static let holdSec: TimeInterval = 0.48 // 全亮定格再收
    private static let outSec: TimeInterval = 0.26 // 收场动画时长

    var body: some View {
        let nodes = deriveNodes()
        HStack(alignment: .top, spacing: 6) {
            ForEach(nodes.indices, id: \.self) { i in
                if i > 0 {
                    connector(prev: nodes[i - 1], next: nodes[i])
                }
                nodeView(nodes[i])
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 9)
        .glassEffect(.regular, in: .rect(cornerRadius: 22))
        .scaleEffect(closing ? 0.88 : 1)
        .opacity(closing ? 0 : 1)
        .animation(.spring(duration: 0.35), value: applied)
        .animation(.easeIn(duration: Self.outSec), value: closing)
        .task(id: "\(applied)/\(events.count)/\(done)") { await advance() }
    }

    // MARK: - 节奏(事件到达≠画面前进)

    private func advance() async {
        if applied < events.count {
            let minGap = done ? Self.fastStep : Self.minStep
            let wait = max(0, minGap - Date().timeIntervalSince(lastStep))
            try? await Task.sleep(for: .seconds(wait))
            guard !Task.isCancelled else { return }
            lastStep = Date()
            applied += 1
            return
        }
        if done, !closing {
            try? await Task.sleep(for: .seconds(Self.holdSec))
            guard !Task.isCancelled else { return }
            closing = true
            try? await Task.sleep(for: .seconds(Self.outSec))
            guard !Task.isCancelled else { return }
            onGone()
        }
    }

    // MARK: - 从已应用的事件推导节点

    private enum NodeState { case pending, active, done }
    private struct Node {
        let key: String
        let label: String
        let icon: String
        let state: NodeState
    }

    private static let trackMeta: [String: (icon: String, label: String)] = [
        "eat": ("fork.knife", "饮食"),
        "exercise": ("dumbbell.fill", "运动"),
        "remember": ("bookmark.fill", "记住"),
    ]

    private func deriveNodes() -> [Node] {
        var tracks: [String]?
        var doneTracks = Set<String>()
        var saving = false
        for e in events.prefix(applied) {
            switch e.stage {
            case "extract": tracks = e.tracks ?? []
            case "track_done": if let t = e.track { doneTracks.insert(t) }
            case "saving": saving = true
            default: break
            }
        }
        // 走到入库才算成功:成功收场全节点点亮;整句失败没有入库事件,保持原状收起
        let finished = done && applied >= events.count && saving

        var nodes = [
            Node(
                key: "triage", label: "理解", icon: "sparkles",
                state: finished || tracks != nil ? .done : .active
            )
        ]
        if let tracks {
            for t in tracks {
                let meta = Self.trackMeta[t] ?? ("sparkles", t)
                nodes.append(
                    Node(
                        key: t, label: meta.label, icon: meta.icon,
                        // 各路并发:出现即活跃;入库开始说明各路都已收束
                        state: finished || saving || doneTracks.contains(t)
                            ? .done : .active
                    ))
            }
            nodes.append(
                Node(
                    key: "saving", label: "入库", icon: "tray.and.arrow.down.fill",
                    state: finished ? .done : saving ? .active : .pending
                ))
        }
        return nodes
    }

    // MARK: - 视图零件

    private func nodeView(_ n: Node) -> some View {
        VStack(spacing: 4) {
            Image(systemName: n.icon)
                .font(.system(size: 12, weight: .bold))
                .foregroundStyle(
                    n.state == .done
                        ? .white
                        : n.state == .active
                            ? Theme.intake : Theme.textSecondary.opacity(0.5)
                )
                .frame(width: 28, height: 28)
                .background(
                    Circle().fill(
                        n.state == .done
                            ? Theme.intake
                            : n.state == .active
                                ? Theme.intake.opacity(0.14) : Color.black.opacity(0.05)
                    )
                )
                .modifier(BreathingWhileActive(active: n.state == .active))
            Text(n.label)
                .font(.system(size: 10))
                .foregroundStyle(
                    n.state == .pending
                        ? Theme.textSecondary.opacity(0.5) : Theme.textSecondary
                )
        }
        .frame(width: 36)
        .transition(.scale.combined(with: .opacity))
    }

    private func connector(prev: Node, next: Node) -> some View {
        let flowing = prev.state == .done && next.state == .active
        return Capsule()
            .fill(
                next.state == .done
                    ? Theme.intake.opacity(0.55)
                    : flowing ? Theme.intake.opacity(0.18) : Color.black.opacity(0.1)
            )
            .frame(width: 14, height: 2)
            .modifier(FlowWhileActive(active: flowing))
            .padding(.top, 13) // 对齐节点圆心(圆28高,线2高)
    }
}

// 当前节点呼吸(仅发送后的几秒存在,是响应式反馈,不是常驻装饰动画)
private struct BreathingWhileActive: ViewModifier {
    let active: Bool
    func body(content: Content) -> some View {
        if active {
            content.phaseAnimator([1.0, 1.12]) { view, scale in
                view.scaleEffect(scale)
            } animation: { _ in .easeInOut(duration: 0.6) }
        } else {
            content
        }
    }
}

// 亮点在连线上流动
private struct FlowWhileActive: ViewModifier {
    let active: Bool
    func body(content: Content) -> some View {
        if active {
            content.overlay {
                GeometryReader { geo in
                    Circle()
                        .fill(Theme.intake)
                        .frame(width: 4, height: 4)
                        .phaseAnimator([0.0, 1.0]) { view, p in
                            view.offset(x: p * (geo.size.width - 4), y: -1)
                        } animation: { _ in .easeInOut(duration: 0.7) }
                }
            }
        } else {
            content
        }
    }
}
