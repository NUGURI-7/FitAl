//
//  ContentView.swift
//  FitAl
//
//  Created by nuguri on 2026/7/9.
//

import SwiftUI

/// 登录门卫(契约 2026-07-12 两道守卫):
/// ①启动时钥匙串无令牌直接进登录页;②任一请求 401 → 接口层清令牌并广播,这里收到即切回登录页。
/// 登录/退出都靠换挂载:主界面整体重挂,状态天然按当前用户重新拉起。
struct ContentView: View {
    @State private var authed = AuthStore.token != nil

    var body: some View {
        Group {
            if authed {
                HomeView(onLoggedOut: { authed = false })
            } else {
                LoginView(onAuthed: { authed = true })
            }
        }
        .animation(.spring(duration: 0.4), value: authed)
        .onReceive(NotificationCenter.default.publisher(for: .fitalUnauthorized)) { _ in
            authed = false
        }
    }
}

#Preview {
    ContentView()
}
