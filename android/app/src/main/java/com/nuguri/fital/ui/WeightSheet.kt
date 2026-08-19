package com.nuguri.fital.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.nuguri.fital.data.Api
import com.nuguri.fital.data.RecordPatch
import com.nuguri.fital.data.WeightPoint
import com.nuguri.fital.ui.theme.Burn
import com.nuguri.fital.ui.theme.Card
import com.nuguri.fital.ui.theme.Paper
import com.nuguri.fital.ui.theme.TextPrimary
import com.nuguri.fital.ui.theme.TextSecondary
import com.nuguri.fital.ui.theme.Weight
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter

/**
 * 体重面板:近三十天曲线 + 记录列表。
 * 点数值就地改,垃圾桶两击删;改删都只落体重表,派生数字读时现算,不联动重算。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WeightSheet(
    weights: List<WeightPoint>,
    onDismiss: () -> Unit,
    onChanged: () -> Unit,
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val scope = rememberCoroutineScope()
    var editingId by remember { mutableStateOf<Int?>(null) }
    var editText by remember { mutableStateOf("") }
    var armedId by remember { mutableStateOf<Int?>(null) }
    var busy by remember { mutableStateOf(false) }
    var errorMsg by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(armedId) {
        if (armedId != null) {
            delay(3000)
            armedId = null
        }
    }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        containerColor = Paper,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
                .imePadding()
                .padding(start = 20.dp, end = 20.dp, bottom = 28.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text("体重 · 近 30 天", fontSize = 17.sp, fontWeight = FontWeight.Bold, color = TextPrimary)
            Spacer(Modifier.height(16.dp))

            if (weights.isEmpty()) {
                Text(
                    "还没有体重记录，说一句「今天 72 公斤」就有了",
                    fontSize = 13.sp,
                    color = TextSecondary,
                    modifier = Modifier.padding(vertical = 40.dp),
                )
            } else {
                WeightChart(weights)
                Spacer(Modifier.height(18.dp))

                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(18.dp))
                        .background(Card)
                        .padding(horizontal = 16.dp),
                ) {
                    weights.asReversed().forEachIndexed { i, p ->
                        Row(
                            modifier = Modifier.fillMaxWidth().padding(vertical = 12.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text(rowDate(p.createdAt), fontSize = 13.sp, color = TextSecondary)
                            Spacer(Modifier.weight(1f))

                            if (editingId == p.id) {
                                TextField(
                                    value = editText,
                                    onValueChange = { editText = it },
                                    singleLine = true,
                                    textStyle = androidx.compose.ui.text.TextStyle(
                                        fontSize = 15.sp,
                                        fontWeight = FontWeight.SemiBold,
                                        color = Weight,
                                        textAlign = TextAlign.End,
                                    ),
                                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                                    colors = TextFieldDefaults.colors(
                                        focusedContainerColor = Color.Transparent,
                                        unfocusedContainerColor = Color.Transparent,
                                        focusedIndicatorColor = Color.Transparent,
                                        unfocusedIndicatorColor = Color.Transparent,
                                    ),
                                    modifier = Modifier.width(96.dp),
                                )
                                Text(
                                    "保存",
                                    fontSize = 13.sp,
                                    fontWeight = FontWeight.SemiBold,
                                    color = Weight,
                                    modifier = Modifier
                                        .clip(RoundedCornerShape(12.dp))
                                        .padding(horizontal = 8.dp, vertical = 4.dp)
                                        .then(
                                            if (busy) Modifier else Modifier.clickableNoRipple {
                                                val v = editText.toDoubleOrNull()
                                                if (v == null || v <= 0) {
                                                    errorMsg = "体重数字不对劲：不能为空、零或负数"
                                                    return@clickableNoRipple
                                                }
                                                if (v == p.weightKg) {
                                                    editingId = null
                                                    return@clickableNoRipple
                                                }
                                                busy = true
                                                errorMsg = null
                                                scope.launch {
                                                    runCatching {
                                                        Api.patchRecord("weight", p.id, RecordPatch(weightKg = v))
                                                    }.fold(
                                                        onSuccess = { editingId = null; onChanged() },
                                                        onFailure = { errorMsg = "保存失败：${it.message}" },
                                                    )
                                                    busy = false
                                                }
                                            }
                                        ),
                                )
                            } else {
                                Text(
                                    "%.1f".format(p.weightKg),
                                    fontSize = 15.sp,
                                    fontWeight = FontWeight.SemiBold,
                                    color = TextPrimary,
                                    modifier = Modifier.clickableNoRipple {
                                        editingId = p.id
                                        editText = "%.1f".format(p.weightKg)
                                    },
                                )
                                Spacer(Modifier.width(3.dp))
                                Text("kg", fontSize = 11.sp, color = TextSecondary)
                            }

                            Spacer(Modifier.width(8.dp))

                            if (armedId == p.id) {
                                ConfirmPill(onClick = {
                                    busy = true
                                    scope.launch {
                                        runCatching { Api.deleteRecord("weight", p.id) }
                                            .fold(
                                                onSuccess = { armedId = null; onChanged() },
                                                onFailure = { errorMsg = "删除失败：${it.message}" },
                                            )
                                        busy = false
                                    }
                                })
                            } else {
                                TrashButton(onClick = { armedId = p.id })
                            }
                        }
                        if (i != weights.lastIndex) {
                            HorizontalDivider(color = TextSecondary.copy(alpha = 0.12f))
                        }
                    }
                }
            }

            errorMsg?.let {
                Text(it, fontSize = 12.sp, color = Burn, modifier = Modifier.padding(top = 12.dp))
            }
        }
    }
}

/** 体重曲线:真实时间轴,线下渐变淡淡晕开 */
@Composable
private fun WeightChart(points: List<WeightPoint>) {
    if (points.size < 2) {
        Text(
            "只有一条记录，再记一次就有曲线了",
            fontSize = 12.sp,
            color = TextSecondary,
            modifier = Modifier.padding(vertical = 24.dp),
        )
        return
    }

    val stamps = remember(points) { points.map { epochOf(it.createdAt) } }
    val minT = stamps.min()
    val maxT = stamps.max()
    val span = (maxT - minT).takeIf { it > 0 } ?: 1L
    val minW = points.minOf { it.weightKg }
    val maxW = points.maxOf { it.weightKg }
    val pad = ((maxW - minW) * 0.15).takeIf { it > 0.05 } ?: 0.5
    val lo = minW - pad
    val hi = maxW + pad

    Canvas(
        modifier = Modifier
            .fillMaxWidth()
            .height(160.dp)
            .clip(RoundedCornerShape(18.dp))
            .background(Card)
            .padding(horizontal = 14.dp, vertical = 16.dp),
    ) {
        fun px(i: Int) = size.width * ((stamps[i] - minT).toFloat() / span.toFloat())
        fun py(v: Double) = size.height * (1f - ((v - lo) / (hi - lo)).toFloat())

        val line = Path().apply {
            points.indices.forEach { i ->
                if (i == 0) moveTo(px(i), py(points[i].weightKg)) else lineTo(px(i), py(points[i].weightKg))
            }
        }
        val area = Path().apply {
            addPath(line)
            lineTo(px(points.lastIndex), size.height)
            lineTo(px(0), size.height)
            close()
        }

        drawPath(
            area,
            Brush.verticalGradient(listOf(Weight.copy(alpha = 0.22f), Weight.copy(alpha = 0f))),
        )
        drawPath(line, Weight, style = Stroke(width = 2.2.dp.toPx(), cap = StrokeCap.Round))
        points.indices.forEach { i ->
            drawCircle(Weight, radius = 3.dp.toPx(), center = Offset(px(i), py(points[i].weightKg)))
            drawCircle(Card, radius = 1.4.dp.toPx(), center = Offset(px(i), py(points[i].weightKg)))
        }
    }
}

private fun rowDate(iso: String): String =
    parseLocal(iso)?.format(DateTimeFormatter.ofPattern("M月d日 HH:mm")) ?: iso

private fun epochOf(iso: String): Long =
    parseLocal(iso)?.atZone(ZoneId.systemDefault())?.toEpochSecond() ?: 0L

/** 后端时间戳形态不定(带不带时区、带不带小数秒),两种都收 */
private fun parseLocal(iso: String): LocalDateTime? = runCatching {
    OffsetDateTime.parse(iso).atZoneSameInstant(ZoneId.systemDefault()).toLocalDateTime()
}.recoverCatching { LocalDateTime.parse(iso) }.getOrNull()

/** 就地编辑的小热区:不要 Material 那圈水波,免得像按钮 */
@Composable
private fun Modifier.clickableNoRipple(onClick: () -> Unit): Modifier {
    val source = remember { MutableInteractionSource() }
    return this.clickable(interactionSource = source, indication = null, onClick = onClick)
}
