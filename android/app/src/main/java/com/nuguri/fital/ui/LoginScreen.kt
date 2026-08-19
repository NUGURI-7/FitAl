package com.nuguri.fital.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import com.nuguri.fital.data.Api
import com.nuguri.fital.ui.theme.Brand
import com.nuguri.fital.ui.theme.Burn
import com.nuguri.fital.ui.theme.Paper
import com.nuguri.fital.ui.theme.TextPrimary
import kotlinx.coroutines.launch

/**
 * 登录 / 注册页。契约 2026-07-12:
 * 注册凭邀请码,一并收身体档案三字段;成功当场发令牌,免二次登录。
 */
@Composable
fun LoginScreen(onAuthenticated: () -> Unit) {
    var isRegister by remember { mutableStateOf(false) }
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var inviteCode by remember { mutableStateOf("") }
    var nickname by remember { mutableStateOf("") }
    var height by remember { mutableStateOf("") }
    var sex by remember { mutableStateOf("male") }
    var birthYear by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    val scope = rememberCoroutineScope()

    fun submit() {
        error = null
        busy = true
        scope.launch {
            val result = runCatching {
                if (isRegister) {
                    val cm = height.trim().toDoubleOrNull() ?: error("身高要填数字,单位厘米")
                    val year = birthYear.trim().toIntOrNull() ?: error("出生年份要填四位数字")
                    Api.register(
                        inviteCode = inviteCode.trim(),
                        username = username.trim(),
                        nickname = nickname.trim().ifBlank { null },
                        password = password,
                        heightCm = cm,
                        sex = sex,
                        birthYear = year,
                    )
                } else {
                    Api.login(username.trim(), password)
                }
            }
            busy = false
            result.fold(
                onSuccess = { onAuthenticated() },
                onFailure = { error = it.message ?: "操作失败" },
            )
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Paper)
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 28.dp, vertical = 48.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            buildAnnotatedString {
                withStyle(SpanStyle(color = TextPrimary)) { append("Fit") }
                withStyle(SpanStyle(color = Brand)) { append("Al") }
                withStyle(SpanStyle(color = Burn)) { append(".") }
            },
            style = MaterialTheme.typography.displaySmall,
            fontWeight = FontWeight.Bold,
        )
        Text(
            "一句话，记下吃和练",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(top = 8.dp),
        )

        Spacer(Modifier.height(36.dp))

        if (isRegister) {
            Field(inviteCode, { inviteCode = it }, "邀请码", "一码注册一人，用过即作废；问管理员要")
        }
        Field(username, { username = it }, "用户名", "字母/数字/下划线，3-20 位，注册后不可改".takeIf { isRegister })
        Field(password, { password = it }, "密码", "最短 6 位".takeIf { isRegister }, isPassword = true)

        if (isRegister) {
            Field(nickname, { nickname = it }, "昵称", "选填，留空用用户名；可重名、可随时改")
            Field(height, { height = it }, "身高（厘米）", null, numeric = true)
            Field(birthYear, { birthYear = it }, "出生年份", "用于基础代谢与消耗计算，之后可在设置里改", numeric = true)

            Row(
                modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("性别", style = MaterialTheme.typography.bodyMedium)
                FilterChip(sex == "male", { sex = "male" }, { Text("男") })
                FilterChip(sex == "female", { sex = "female" }, { Text("女") })
            }
        }

        error?.let {
            Text(
                it,
                style = MaterialTheme.typography.bodyMedium,
                color = Burn,
                modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
            )
        }

        Spacer(Modifier.height(28.dp))

        Button(
            onClick = ::submit,
            enabled = !busy && username.isNotBlank() && password.isNotBlank(),
            modifier = Modifier.fillMaxWidth().height(52.dp),
        ) {
            if (busy) {
                CircularProgressIndicator(
                    modifier = Modifier.height(20.dp),
                    color = MaterialTheme.colorScheme.onPrimary,
                    strokeWidth = 2.dp,
                )
            } else {
                Text(if (isRegister) "注册" else "登录")
            }
        }

        TextButton(
            onClick = { isRegister = !isRegister; error = null },
            enabled = !busy,
            modifier = Modifier.padding(top = 8.dp),
        ) {
            Text(if (isRegister) "已有账号，去登录" else "有邀请码，去注册")
        }
    }
}

@Composable
private fun Field(
    value: String,
    onChange: (String) -> Unit,
    label: String,
    hint: String? = null,
    isPassword: Boolean = false,
    numeric: Boolean = false,
) {
    Column(modifier = Modifier.fillMaxWidth().padding(top = 12.dp)) {
        OutlinedTextField(
            value = value,
            onValueChange = onChange,
            label = { Text(label) },
            singleLine = true,
            visualTransformation =
                if (isPassword) PasswordVisualTransformation() else androidx.compose.ui.text.input.VisualTransformation.None,
            keyboardOptions = KeyboardOptions(
                keyboardType = when {
                    isPassword -> KeyboardType.Password
                    numeric -> KeyboardType.Number
                    else -> KeyboardType.Text
                }
            ),
            modifier = Modifier.fillMaxWidth(),
        )
        hint?.let {
            Text(
                it,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(start = 4.dp, top = 4.dp),
            )
        }
    }
}
