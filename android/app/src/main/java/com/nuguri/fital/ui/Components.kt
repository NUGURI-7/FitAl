package com.nuguri.fital.ui

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.LocalTextStyle
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.nuguri.fital.ui.theme.Card
import com.nuguri.fital.ui.theme.Paper
import com.nuguri.fital.ui.theme.TextPrimary
import com.nuguri.fital.ui.theme.TextSecondary

/**
 * 纸感底 + 两团极淡柔光。
 * 静态不做循环动画:常驻动画费电占 GPU,与 iOS 同口径(2026-07-09 砍定)。
 */
@Composable
fun BreathingBackground(brand: Color, burn: Color, modifier: Modifier = Modifier) {
    Canvas(modifier = modifier.fillMaxSize().background(Paper)) {
        drawRect(
            brush = Brush.radialGradient(
                colors = listOf(brand.copy(alpha = 0.09f), brand.copy(alpha = 0f)),
                center = Offset(size.width * 0.18f, size.height * 0.10f),
                radius = 460f,
            ),
        )
        drawRect(
            brush = Brush.radialGradient(
                colors = listOf(burn.copy(alpha = 0.07f), burn.copy(alpha = 0f)),
                center = Offset(size.width * 0.86f, size.height * 0.42f),
                radius = 420f,
            ),
        )
    }
}

/** 卡片依次浮现:上浮 + 缩放 + 渐显,按次序错开 */
@Composable
fun Modifier.entrance(appeared: Boolean, index: Int): Modifier {
    val spec = spring<Float>(dampingRatio = 0.78f, stiffness = 190f)
    val progress by animateFloatAsState(
        targetValue = if (appeared) 1f else 0f,
        animationSpec = spec,
        label = "entrance$index",
    )
    return this
        .alpha(progress)
        .scale(0.97f + 0.03f * progress)
}

/** 指标卡:左上标题、大字数值、右上角配件(进度环 / 趋势线),右上有一团同色光晕 */
@Composable
fun StatTile(
    title: String,
    value: String,
    unit: String,
    sub: String,
    color: Color,
    modifier: Modifier = Modifier,
    gradientNumber: Boolean = false,
    accessory: @Composable () -> Unit = {},
) {
    Box(
        modifier = modifier
            .shadow(6.dp, RoundedCornerShape(18.dp), spotColor = Color.Black.copy(alpha = 0.12f))
            .clip(RoundedCornerShape(18.dp))
            .background(Card),
    ) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            drawRect(
                brush = Brush.radialGradient(
                    colors = listOf(color.copy(alpha = 0.20f), color.copy(alpha = 0f)),
                    center = Offset(size.width * 0.94f, size.height * 0.06f),
                    radius = 130f,
                ),
            )
        }

        Box(modifier = Modifier.align(Alignment.TopEnd).padding(8.dp)) { accessory() }

        Column(modifier = Modifier.fillMaxSize().padding(horizontal = 10.dp, vertical = 11.dp)) {
            Text(title, fontSize = 11.sp, fontWeight = FontWeight.Medium, color = color)
            Spacer(Modifier.height(2.dp))
            Row(verticalAlignment = Alignment.Bottom) {
                Text(
                    value,
                    fontSize = 21.sp,
                    fontWeight = FontWeight.Bold,
                    color = if (gradientNumber) Color.Unspecified else TextPrimary,
                    style = if (gradientNumber) {
                        LocalTextStyle.current.copy(
                            brush = Brush.verticalGradient(
                                listOf(color, color.copy(alpha = 0.55f))
                            )
                        )
                    } else LocalTextStyle.current,
                    maxLines = 1,
                    softWrap = false,
                )
                Spacer(Modifier.width(2.dp))
                Text(
                    unit,
                    fontSize = 9.5.sp,
                    color = TextSecondary,
                    maxLines = 1,
                    softWrap = false,
                    modifier = Modifier.padding(bottom = 3.dp),
                )
            }
            Spacer(Modifier.weight(1f))
            Text(
                sub.ifBlank { " " },
                fontSize = 9.sp,
                color = TextSecondary.copy(alpha = 0.8f),
                maxLines = 1,
                softWrap = false,
            )
        }
    }
}

/** 细进度环:消耗占基础代谢的比例 */
@Composable
fun ProgressRing(progress: Float, color: Color, modifier: Modifier = Modifier) {
    val p by animateFloatAsState(progress.coerceIn(0f, 1f), label = "ring")
    Canvas(modifier = modifier.size(22.dp)) {
        val stroke = Stroke(width = 2.5.dp.toPx(), cap = StrokeCap.Round)
        drawArc(
            color = color.copy(alpha = 0.18f),
            startAngle = 0f, sweepAngle = 360f, useCenter = false, style = stroke,
        )
        drawArc(
            color = color,
            startAngle = -90f, sweepAngle = 360f * p, useCenter = false, style = stroke,
        )
    }
}

/** 迷你趋势线:体重最近几次的走向 */
@Composable
fun Sparkline(values: List<Double>, color: Color, modifier: Modifier = Modifier) {
    if (values.size < 2) return
    Canvas(modifier = modifier.width(44.dp).height(16.dp)) {
        val min = values.min()
        val max = values.max()
        val span = (max - min).takeIf { it > 0.0001 } ?: 1.0
        val stepX = size.width / (values.size - 1)
        val path = Path()
        values.forEachIndexed { i, v ->
            val x = stepX * i
            val y = size.height * (1f - ((v - min) / span).toFloat())
            if (i == 0) path.moveTo(x, y) else path.lineTo(x, y)
        }
        drawPath(path, color, style = Stroke(width = 1.6.dp.toPx(), cap = StrokeCap.Round))
    }
}

/** 大卡:圆形渐变图标 + 标题 + 合计,内部再按分组排 */
@Composable
fun SectionCard(
    title: String,
    totalKcal: Int,
    color: Color,
    icon: SectionIcon,
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .shadow(8.dp, RoundedCornerShape(24.dp), spotColor = Color.Black.copy(alpha = 0.12f))
            .clip(RoundedCornerShape(24.dp))
            .background(Card)
            .padding(18.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                modifier = Modifier
                    .size(30.dp)
                    .clip(CircleShape)
                    .background(
                        Brush.linearGradient(listOf(color.copy(alpha = 0.85f), color))
                    ),
                contentAlignment = Alignment.Center,
            ) {
                SectionGlyph(icon)
            }
            Spacer(Modifier.width(8.dp))
            Text(title, fontSize = 17.sp, fontWeight = FontWeight.Bold, color = TextPrimary)
            Spacer(Modifier.weight(1f))
            Text("$totalKcal", fontSize = 17.sp, fontWeight = FontWeight.Bold, color = color)
            Spacer(Modifier.width(3.dp))
            Text("千卡", fontSize = 12.sp, color = TextSecondary, modifier = Modifier.padding(bottom = 2.dp))
        }
        content()
    }
}

enum class SectionIcon { Diet, Exercise }

/** 卡头的小图形:餐具与火苗,自己画,不引整套图标依赖 */
@Composable
private fun SectionGlyph(icon: SectionIcon) {
    Canvas(modifier = Modifier.size(15.dp)) {
        val w = size.width
        val h = size.height
        when (icon) {
            SectionIcon.Diet -> {
                val stroke = Stroke(width = w * 0.11f, cap = StrokeCap.Round)
                // 叉:三根短齿加一根柄
                listOf(0.16f, 0.30f, 0.44f).forEach { fx ->
                    drawLine(Color.White, Offset(w * fx, h * 0.08f), Offset(w * fx, h * 0.36f), stroke.width, StrokeCap.Round)
                }
                drawLine(Color.White, Offset(w * 0.30f, h * 0.36f), Offset(w * 0.30f, h * 0.94f), stroke.width, StrokeCap.Round)
                // 刀
                drawLine(Color.White, Offset(w * 0.80f, h * 0.08f), Offset(w * 0.80f, h * 0.94f), stroke.width, StrokeCap.Round)
                drawLine(Color.White, Offset(w * 0.68f, h * 0.20f), Offset(w * 0.80f, h * 0.46f), stroke.width, StrokeCap.Round)
            }

            SectionIcon.Exercise -> {
                // 哑铃:中间横杆,两端各一对配重
                drawLine(Color.White, Offset(w * 0.30f, h * 0.5f), Offset(w * 0.70f, h * 0.5f), w * 0.10f, StrokeCap.Round)
                listOf(0.20f, 0.80f).forEach { x ->
                    drawLine(Color.White, Offset(w * x, h * 0.22f), Offset(w * x, h * 0.78f), w * 0.16f, StrokeCap.Round)
                }
                listOf(0.06f, 0.94f).forEach { x ->
                    drawLine(Color.White, Offset(w * x, h * 0.34f), Offset(w * x, h * 0.66f), w * 0.12f, StrokeCap.Round)
                }
            }
        }
    }
}

/** 组头:餐次或场次的名字、条数、该组合计 */
@Composable
fun GroupHeader(name: String, count: Int, kcal: Int) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(top = 14.dp, bottom = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(name, fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = TextSecondary)
        Spacer(Modifier.width(6.dp))
        Text("$count 条", fontSize = 11.sp, color = TextSecondary.copy(alpha = 0.7f))
        Spacer(Modifier.weight(1f))
        Text("$kcal 千卡", fontSize = 12.sp, fontWeight = FontWeight.Medium, color = TextSecondary)
    }
}

/** 明细行:同色小圆点 + 名字 + 用量说明 + 热量 */
@Composable
fun ItemRow(
    name: String,
    detail: String,
    kcal: Int,
    color: Color,
    indent: Boolean = false,
    bold: Boolean = false,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(start = if (indent) 14.dp else 0.dp, top = 8.dp, bottom = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier
                .size(5.dp)
                .clip(CircleShape)
                .background(color.copy(alpha = 0.5f)),
        )
        Spacer(Modifier.width(10.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                name,
                fontSize = 15.sp,
                fontWeight = if (bold) FontWeight.SemiBold else FontWeight.Medium,
                color = TextPrimary,
            )
            if (detail.isNotBlank()) {
                Text(detail, fontSize = 12.sp, color = TextSecondary)
            }
        }
        Text("$kcal", fontSize = 15.sp, fontWeight = FontWeight.SemiBold, color = TextPrimary)
    }
}

/** 空态:不摆插画,一句话就够 */
@Composable
fun EmptyHint(text: String) {
    Box(modifier = Modifier.fillMaxWidth().padding(top = 48.dp), contentAlignment = Alignment.Center) {
        Text(text, style = MaterialTheme.typography.bodyMedium, color = TextSecondary)
    }
}
