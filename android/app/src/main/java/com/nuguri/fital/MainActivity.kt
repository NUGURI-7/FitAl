package com.nuguri.fital

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.nuguri.fital.data.Api
import com.nuguri.fital.data.AuthStore
import com.nuguri.fital.ui.LoginScreen
import com.nuguri.fital.ui.theme.FitAlTheme
import com.nuguri.fital.ui.theme.Paper
import kotlinx.coroutines.launch

/** 门卫的三种状态:启动时读本地令牌尚未有结果 / 未登录 / 已登录 */
private enum class Gate { Checking, LoggedOut, LoggedIn }

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        AuthStore.init(this)
        enableEdgeToEdge()
        setContent {
            FitAlTheme {
                Scaffold(
                    modifier = Modifier.fillMaxSize(),
                    containerColor = Paper,
                ) { innerPadding ->
                    Root(modifier = Modifier.padding(innerPadding))
                }
            }
        }
    }
}

/**
 * 前端两道守卫(契约 2026-07-12):
 * 启动时本地无令牌直接进登录页;任何请求收到 401 即清令牌、整界面切回登录页。
 */
@Composable
private fun Root(modifier: Modifier = Modifier) {
    var gate by remember { mutableStateOf(Gate.Checking) }

    LaunchedEffect(Unit) {
        gate = if (AuthStore.token() != null) Gate.LoggedIn else Gate.LoggedOut
    }

    LaunchedEffect(Unit) {
        AuthStore.unauthorized.collect { gate = Gate.LoggedOut }
    }

    when (gate) {
        Gate.Checking -> Unit
        Gate.LoggedOut -> LoginScreen(onAuthenticated = { gate = Gate.LoggedIn })
        Gate.LoggedIn -> HomePlaceholder(
            modifier = modifier,
            onLoggedOut = { gate = Gate.LoggedOut },
        )
    }
}

/** 主干界面尚未实现,先证明带令牌的请求能通、退出登录能回到登录页 */
@Composable
private fun HomePlaceholder(modifier: Modifier = Modifier, onLoggedOut: () -> Unit) {
    var probe by remember { mutableStateOf("请求中…") }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) {
        probe = runCatching { Api.health() }.getOrElse { it.message ?: "失败" }
    }

    Column(
        modifier = modifier.fillMaxSize().background(Paper).padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp, Alignment.CenterVertically),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("已登录", style = MaterialTheme.typography.headlineSmall)
        Text(probe, style = MaterialTheme.typography.bodyLarge)
        TextButton(onClick = { scope.launch { Api.logout(); onLoggedOut() } }) {
            Text("退出登录")
        }
    }
}
