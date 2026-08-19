package com.nuguri.fital.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import com.nuguri.fital.ui.theme.Brand
import com.nuguri.fital.ui.theme.Card
import com.nuguri.fital.ui.theme.TextSecondary

/**
 * 底部输入条:说一句话即记一条。
 * 发送期间显示后端推来的处理进度,处理完显示一句模板回执。
 */
@Composable
fun ChatBar(
    busy: Boolean,
    status: String?,
    reply: String?,
    onSend: (String) -> Unit,
) {
    var text by remember { mutableStateOf("") }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(Card)
            .imePadding()
            .navigationBarsPadding()
            .padding(horizontal = 16.dp, vertical = 10.dp),
    ) {
        AnimatedVisibility(visible = status != null || reply != null) {
            Text(
                text = status ?: reply.orEmpty(),
                style = MaterialTheme.typography.bodySmall,
                color = if (status != null) Brand else TextSecondary,
                modifier = Modifier.padding(start = 4.dp, bottom = 8.dp),
            )
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalAlignment = Alignment.Bottom,
        ) {
            OutlinedTextField(
                value = text,
                onValueChange = { text = it },
                placeholder = { Text("说一句，比如「中午吃了200克鸡胸肉」") },
                enabled = !busy,
                maxLines = 4,
                shape = RoundedCornerShape(24.dp),
                modifier = Modifier.weight(1f).heightIn(min = 52.dp),
            )

            FilledIconButton(
                onClick = {
                    val t = text.trim()
                    if (t.isNotEmpty()) {
                        onSend(t)
                        text = ""
                    }
                },
                enabled = !busy && text.isNotBlank(),
                colors = IconButtonDefaults.filledIconButtonColors(containerColor = Brand),
                modifier = Modifier.size(52.dp),
            ) {
                if (busy) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(20.dp),
                        color = MaterialTheme.colorScheme.onPrimary,
                        strokeWidth = 2.dp,
                    )
                } else {
                    Icon(SendIcon, contentDescription = "发送")
                }
            }
        }
    }
}

/** 发送图标:Material Symbols 的 send 路径,不引整套图标依赖 */
private val SendIcon: ImageVector by lazy {
    ImageVector.Builder(
        name = "Send",
        defaultWidth = 24.dp,
        defaultHeight = 24.dp,
        viewportWidth = 24f,
        viewportHeight = 24f,
    ).apply {
        addPath(
            pathData = androidx.compose.ui.graphics.vector.PathParser()
                .parsePathString("M2.01 21L23 12 2.01 3 2 10l15 2-15 2z")
                .toNodes(),
            fill = androidx.compose.ui.graphics.SolidColor(androidx.compose.ui.graphics.Color.White),
        )
    }.build()
}
