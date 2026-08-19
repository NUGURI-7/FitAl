package com.nuguri.fital.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.PathParser
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.nuguri.fital.ui.theme.Brand
import com.nuguri.fital.ui.theme.Burn
import com.nuguri.fital.ui.theme.Card
import com.nuguri.fital.ui.theme.Paper
import com.nuguri.fital.ui.theme.TextSecondary

/**
 * 底部输入条:说一句话即记一条。
 * 浮在纸感底上——胶囊输入框加一枚独立圆形发送键(与 iOS 同形态);
 * 麦克风嵌在输入框右缘,点开点关,录音时转暖橙并跟着音量抖。
 */
@Composable
fun ChatBar(
    text: String,
    onTextChange: (String) -> Unit,
    busy: Boolean,
    reply: String?,
    recording: Boolean,
    level: Float,
    onMic: () -> Unit,
    onSettings: () -> Unit,
    onSend: (String) -> Unit,
    above: @Composable () -> Unit = {},
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(
                Brush.verticalGradient(
                    listOf(Paper.copy(alpha = 0f), Paper.copy(alpha = 0.92f), Paper)
                )
            )
            .imePadding()
            .padding(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 6.dp),
    ) {
        above()

        AnimatedVisibility(visible = reply != null) {
            Text(
                text = reply.orEmpty(),
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.padding(start = 12.dp, end = 12.dp, bottom = 8.dp),
            )
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.Bottom,
        ) {
            GearButton(onClick = onSettings, modifier = Modifier.padding(bottom = 3.dp))

            Box(modifier = Modifier.weight(1f), contentAlignment = Alignment.CenterEnd) {
                OutlinedTextField(
                    value = text,
                    onValueChange = onTextChange,
                    placeholder = { Text(if (recording) "在听……" else "说一句，记一笔") },
                    enabled = !busy,
                    maxLines = 4,
                    shape = RoundedCornerShape(23.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedContainerColor = Card,
                        unfocusedContainerColor = Card,
                        disabledContainerColor = Card,
                        focusedBorderColor = Color.Transparent,
                        unfocusedBorderColor = Color.Transparent,
                        disabledBorderColor = Color.Transparent,
                    ),
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = 46.dp)
                        .shadow(6.dp, RoundedCornerShape(23.dp), spotColor = Color.Black.copy(alpha = 0.14f)),
                )

                MicButton(recording = recording, level = level, onClick = onMic)
            }

            FilledIconButton(
                onClick = {
                    val t = text.trim()
                    if (t.isNotEmpty()) {
                        onSend(t)
                        onTextChange("")
                    }
                },
                enabled = !busy && text.isNotBlank(),
                colors = IconButtonDefaults.filledIconButtonColors(
                    containerColor = Brand,
                    disabledContainerColor = Brand.copy(alpha = 0.35f),
                ),
                modifier = Modifier.size(46.dp),
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

/** 麦克风:嵌在输入框右缘;录音时橙色底 + 呼吸圈,里面换成跟音量走的声波条 */
@Composable
private fun MicButton(recording: Boolean, level: Float, onClick: () -> Unit) {
    val breathe = rememberInfiniteTransition(label = "mic")
    val pulse by breathe.animateFloat(
        initialValue = 1f,
        targetValue = 1.14f,
        animationSpec = infiniteRepeatable(tween(760), RepeatMode.Reverse),
        label = "micPulse",
    )
    val amp by animateFloatAsState(level, tween(90), label = "amp")

    Box(
        modifier = Modifier
            .padding(end = 6.dp)
            .scale(if (recording) pulse else 1f)
            .size(34.dp)
            .clip(CircleShape)
            .background(if (recording) Burn else Color.Transparent)
            .clickableNoRipple(onClick),
        contentAlignment = Alignment.Center,
    ) {
        if (recording) {
            Canvas(modifier = Modifier.size(16.dp)) {
                val bars = listOf(0.45f, 0.8f, 1f, 0.7f)
                val gap = size.width / bars.size
                bars.forEachIndexed { i, w ->
                    val h = size.height * (0.22f + 0.78f * (amp * w).coerceIn(0f, 1f))
                    val x = gap * (i + 0.5f)
                    drawLine(
                        Color.White,
                        Offset(x, size.height / 2 - h / 2),
                        Offset(x, size.height / 2 + h / 2),
                        strokeWidth = size.width * 0.13f,
                        cap = StrokeCap.Round,
                    )
                }
            }
        } else {
            Canvas(modifier = Modifier.size(17.dp)) {
                val c = TextSecondary
                val w = size.width
                val h = size.height
                // 话筒头 + 支架
                drawRoundRect(
                    color = c,
                    topLeft = Offset(w * 0.34f, h * 0.06f),
                    size = androidx.compose.ui.geometry.Size(w * 0.32f, h * 0.52f),
                    cornerRadius = androidx.compose.ui.geometry.CornerRadius(w * 0.16f),
                )
                drawArc(
                    color = c,
                    startAngle = 0f,
                    sweepAngle = 180f,
                    useCenter = false,
                    topLeft = Offset(w * 0.18f, h * 0.34f),
                    size = androidx.compose.ui.geometry.Size(w * 0.64f, h * 0.44f),
                    style = androidx.compose.ui.graphics.drawscope.Stroke(width = w * 0.10f, cap = StrokeCap.Round),
                )
                drawLine(c, Offset(w * 0.5f, h * 0.78f), Offset(w * 0.5f, h * 0.94f), w * 0.10f, StrokeCap.Round)
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
