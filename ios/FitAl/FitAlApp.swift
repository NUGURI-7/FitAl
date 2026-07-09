//
//  FitAlApp.swift
//  FitAl
//
//  Created by nuguri on 2026/7/9.
//

import SwiftUI

@main
struct FitAlApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
                .preferredColorScheme(.light) // 不做深色设计,锁浅色防系统组件混搭(2026-07-09 用户定)
        }
    }
}
