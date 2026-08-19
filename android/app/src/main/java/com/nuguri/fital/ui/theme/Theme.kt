package com.nuguri.fital.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

// 契约:Material 3 只作组件基座,不使用 M3 默认配色与动态取色;
// 不做深色模式(与 iOS / Web 一致,质感在浅色纸感体系内做)。
private val PaperColorScheme = lightColorScheme(
    primary = Brand,
    onPrimary = Card,
    secondary = Weight,
    tertiary = Burn,
    background = Paper,
    onBackground = TextPrimary,
    surface = Card,
    onSurface = TextPrimary,
    onSurfaceVariant = TextSecondary,
    outline = TextSecondary,
)

@Composable
fun FitAlTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = PaperColorScheme,
        typography = Typography,
        content = content,
    )
}
