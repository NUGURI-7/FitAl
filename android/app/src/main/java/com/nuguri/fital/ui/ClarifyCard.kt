package com.nuguri.fital.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.nuguri.fital.data.Api
import com.nuguri.fital.data.ChatClarify
import com.nuguri.fital.ui.theme.Brand
import com.nuguri.fital.ui.theme.Burn
import com.nuguri.fital.ui.theme.Card
import com.nuguri.fital.ui.theme.Paper
import com.nuguri.fital.ui.theme.TextPrimary
import com.nuguri.fital.ui.theme.TextSecondary
import kotlinx.coroutines.launch

/**
 * 澄清小表单(契约 event:clarify):罕见兜底——运动段缺数,连估都估不出时浮出。
 * 问题固定=一句问话 + 数字输入框 + 单位,不做通用表单。
 * 收起不影响数据:待补段躺在服务器上,不填也不过期。
 */
@Composable
fun ClarifyCard(
    clarify: ChatClarify,
    onDone: (String) -> Unit,
    onDismiss: () -> Unit,
) {
    val values = remember(clarify.inputId) { mutableStateMapOf<String, String>() }
    var submitting by remember { mutableStateOf(false) }
    var errorMsg by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    // 只提交填了正数的格子;后端重跑同套校验,没填够会打回
    val answers = clarify.questions.mapNotNull { q ->
        values[q.key]?.toDoubleOrNull()?.takeIf { it > 0 }?.let { q.key to it }
    }.toMap()

    val ready = answers.size >= clarify.minAnswers &&
        clarify.questions.all { !it.required || answers.containsKey(it.key) }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(bottom = 8.dp)
            .shadow(8.dp, RoundedCornerShape(20.dp), spotColor = Color.Black.copy(alpha = 0.14f))
            .clip(RoundedCornerShape(20.dp))
            .background(Card)
            .padding(16.dp),
    ) {
        Row(verticalAlignment = Alignment.Top) {
            Box(
                modifier = Modifier.size(20.dp).clip(CircleShape).background(Brand),
                contentAlignment = Alignment.Center,
            ) {
                Text("?", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color.White)
            }
            Spacer(Modifier.width(8.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text("还差个数才能记上", fontSize = 14.sp, fontWeight = FontWeight.Bold, color = TextPrimary)
                Text(
                    "「${clarify.text}」",
                    fontSize = 12.sp,
                    color = TextSecondary,
                    maxLines = 1,
                )
            }
            Text(
                "×",
                fontSize = 18.sp,
                color = TextSecondary,
                modifier = Modifier
                    .clip(CircleShape)
                    .clickableNoRipple(onDismiss)
                    .padding(horizontal = 8.dp),
            )
        }

        if (clarify.minAnswers == 1 && clarify.questions.size > 1) {
            Text(
                "两个填一个就行",
                fontSize = 11.sp,
                color = TextSecondary,
                modifier = Modifier.padding(top = 6.dp),
            )
        }

        clarify.questions.forEach { q ->
            Row(
                modifier = Modifier.fillMaxWidth().padding(top = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(q.prompt, fontSize = 13.sp, color = TextPrimary, maxLines = 1)
                Spacer(Modifier.weight(1f))
                TextField(
                    value = values[q.key].orEmpty(),
                    onValueChange = { values[q.key] = it },
                    singleLine = true,
                    textStyle = androidx.compose.ui.text.TextStyle(
                        fontSize = 14.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = Brand,
                        textAlign = TextAlign.End,
                    ),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    colors = TextFieldDefaults.colors(
                        focusedContainerColor = Paper,
                        unfocusedContainerColor = Paper,
                        focusedIndicatorColor = Color.Transparent,
                        unfocusedIndicatorColor = Color.Transparent,
                    ),
                    shape = RoundedCornerShape(12.dp),
                    modifier = Modifier.width(96.dp).height(48.dp),
                )
                Spacer(Modifier.width(6.dp))
                Text(q.unit, fontSize = 12.sp, color = TextSecondary)
            }
        }

        errorMsg?.let {
            Text(it, fontSize = 12.sp, color = Burn, modifier = Modifier.padding(top = 8.dp))
        }

        Button(
            onClick = {
                submitting = true
                errorMsg = null
                scope.launch {
                    runCatching { Api.submitClarify(clarify.inputId, answers) }
                        .fold(
                            onSuccess = onDone,
                            onFailure = {
                                errorMsg = it.message ?: "补交失败"
                                submitting = false
                            },
                        )
                }
            },
            enabled = ready && !submitting,
            colors = ButtonDefaults.buttonColors(containerColor = Brand),
            shape = RoundedCornerShape(14.dp),
            modifier = Modifier.fillMaxWidth().height(44.dp).padding(top = 0.dp),
        ) {
            if (submitting) {
                CircularProgressIndicator(Modifier.size(18.dp), Color.White, 2.dp)
            } else {
                Text("补上", fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
            }
        }
    }
}
