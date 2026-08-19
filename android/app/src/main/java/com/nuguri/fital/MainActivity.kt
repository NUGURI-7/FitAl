package com.nuguri.fital

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.nuguri.fital.data.Api
import com.nuguri.fital.ui.theme.FitAlTheme

/** 探活的三种结局,界面按这个分支显示 */
private sealed interface Health {
    data object Loading : Health
    data class Ok(val body: String) : Health
    data class Failed(val reason: String) : Health
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            FitAlTheme {
                Scaffold(modifier = Modifier.fillMaxSize()) { innerPadding ->
                    HealthProbe(modifier = Modifier.padding(innerPadding))
                }
            }
        }
    }
}

@Composable
private fun HealthProbe(modifier: Modifier = Modifier) {
    var state: Health by remember { mutableStateOf(Health.Loading) }

    LaunchedEffect(Unit) {
        state = runCatching { Api.health() }
            .fold(
                onSuccess = { Health.Ok(it) },
                onFailure = { Health.Failed(it.message ?: it.javaClass.simpleName) },
            )
    }

    Column(
        modifier = modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp, Alignment.CenterVertically),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        when (val s = state) {
            Health.Loading -> Text("正在连接后端…", style = MaterialTheme.typography.titleMedium)
            is Health.Ok -> {
                Text("后端连通", style = MaterialTheme.typography.headlineSmall)
                Text(s.body, style = MaterialTheme.typography.bodyLarge)
            }
            is Health.Failed -> {
                Text("连接失败", style = MaterialTheme.typography.headlineSmall)
                Text(s.reason, style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}
