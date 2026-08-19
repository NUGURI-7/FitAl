package com.nuguri.fital

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import com.nuguri.fital.data.AuthStore
import com.nuguri.fital.ui.HomeScreen
import com.nuguri.fital.ui.LoginScreen
import com.nuguri.fital.ui.theme.FitAlTheme
import com.nuguri.fital.ui.theme.Paper

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

    Box(modifier = modifier.fillMaxSize()) {
        when (gate) {
            Gate.Checking -> Unit
            Gate.LoggedOut -> LoginScreen(onAuthenticated = { gate = Gate.LoggedIn })
            Gate.LoggedIn -> HomeScreen(onLoggedOut = { gate = Gate.LoggedOut })
        }
    }
}
