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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.PathParser
import androidx.compose.ui.unit.dp
import com.nuguri.fital.ui.theme.Brand
import com.nuguri.fital.ui.theme.Card
import com.nuguri.fital.ui.theme.Paper
import com.nuguri.fital.ui.theme.TextSecondary

/**
 * 底部输入条:说一句话即记一条。
 * 浮在纸感底上——胶囊输入框加一枚独立圆形发送键,不做整条白色横栏(与 iOS 同形态)。
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
            .background(
                Brush.verticalGradient(
                    listOf(Paper.copy(alpha = 0f), Paper.copy(alpha = 0.92f), Paper)
                )
            )
            .imePadding()
            .navigationBarsPadding()
            .padding(start = 16.dp, end = 16.dp, top = 18.dp, bottom = 12.dp),
    ) {
        AnimatedVisibility(visible = status != null || reply != null) {
            Text(
                text = status ?: reply.orEmpty(),
                style = MaterialTheme.typography.bodySmall,
                color = if (status != null) Brand else TextSecondary,
                modifier = Modifier.padding(start = 12.dp, bottom = 8.dp),
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
                placeholder = { Text("说一句，记一笔") },
                enabled = !busy,
                maxLines = 4,
                shape = RoundedCornerShape(26.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedContainerColor = Card,
                    unfocusedContainerColor = Card,
                    disabledContainerColor = Card,
                    focusedBorderColor = Color.Transparent,
                    unfocusedBorderColor = Color.Transparent,
                    disabledBorderColor = Color.Transparent,
                ),
                modifier = Modifier
                    .weight(1f)
                    .heightIn(min = 52.dp)
                    .shadow(6.dp, RoundedCornerShape(26.dp), spotColor = Color.Black.copy(alpha = 0.14f)),
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
                colors = IconButtonDefaults.filledIconButtonColors(
                    containerColor = Brand,
                    disabledContainerColor = Brand.copy(alpha = 0.35f),
                ),
                modifier = Modifier.size(52.dp),
            ) {
                if (busy) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(20.dp),
                        color = Color.White,
                        strokeWidth = 2.dp,
                    )
                } else {
                    Icon(ArrowUpIcon, contentDescription = "发送", tint = Color.White)
                }
            }
        }
    }
}

/** 向上箭头:与 iOS 发送键同形,自己画,不引整套图标依赖 */
private val ArrowUpIcon: ImageVector by lazy {
    ImageVector.Builder(
        name = "ArrowUp",
        defaultWidth = 24.dp,
        defaultHeight = 24.dp,
        viewportWidth = 24f,
        viewportHeight = 24f,
    ).apply {
        addPath(
            pathData = PathParser()
                .parsePathString("M12 4l-7 7 1.4 1.4L11 7.8V20h2V7.8l4.6 4.6L19 11z")
                .toNodes(),
            fill = androidx.compose.ui.graphics.SolidColor(Color.White),
        )
    }.build()
}
