package com.nuguri.fital.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.nuguri.fital.data.Api
import com.nuguri.fital.data.ExerciseItem
import com.nuguri.fital.data.FoodItem
import com.nuguri.fital.data.RecordPatch
import com.nuguri.fital.data.cleanFoodName
import com.nuguri.fital.ui.theme.Brand
import com.nuguri.fital.ui.theme.Burn
import com.nuguri.fital.ui.theme.Card
import com.nuguri.fital.ui.theme.Paper
import com.nuguri.fital.ui.theme.TextPrimary
import com.nuguri.fital.ui.theme.TextSecondary
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlin.math.roundToInt

/** 被点开的那条记录:饮食或运动 */
sealed interface Selected {
    data class Food(val item: FoodItem) : Selected
    data class Exercise(val item: ExerciseItem) : Selected
}

/**
 * 记录详情卡(底部弹起):展示 + 修改 + 删除。
 * 改克数、负重、次数、时长 → 后端按规矩重算热量;直接改热量 → 采用用户报的数。
 * 删除两击确认,三秒不点自动缩回;改删成功后关卡,主页静默刷新。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RecordSheet(selected: Selected, onDismiss: () -> Unit, onChanged: () -> Unit) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val scope = rememberCoroutineScope()

    val isFood = selected is Selected.Food
    val kind = if (isFood) "food" else "exercise"
    val id = when (selected) {
        is Selected.Food -> selected.item.id
        is Selected.Exercise -> selected.item.id
    }
    val color = if (isFood) Brand else Burn

    val origin = remember(selected) {
        when (selected) {
            is Selected.Food -> Origin(
                grams = selected.item.grams.clean(),
                kcal = selected.item.kcal.clean(),
            )

            is Selected.Exercise -> Origin(
                load = selected.item.loadKg.clean(),
                reps = selected.item.reps?.toString().orEmpty(),
                duration = selected.item.durationMin?.let { "%.1f".format(it) }.orEmpty(),
                kcal = selected.item.kcal.clean(),
            )
        }
    }

    var grams by remember(selected) { mutableStateOf(origin.grams) }
    var load by remember(selected) { mutableStateOf(origin.load) }
    var reps by remember(selected) { mutableStateOf(origin.reps) }
    var duration by remember(selected) { mutableStateOf(origin.duration) }
    var kcal by remember(selected) { mutableStateOf(origin.kcal) }
    var busy by remember { mutableStateOf(false) }
    var errorMsg by remember { mutableStateOf<String?>(null) }
    var confirmingDelete by remember { mutableStateOf(false) }

    val dirty = grams != origin.grams || load != origin.load ||
        reps != origin.reps || duration != origin.duration || kcal != origin.kcal

    LaunchedEffect(confirmingDelete) {
        if (confirmingDelete) {
            delay(3000)
            confirmingDelete = false
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
            Text(
                when (selected) {
                    is Selected.Food -> cleanFoodName(selected.item.foodName)
                    is Selected.Exercise -> selected.item.exerciseName
                },
                fontSize = 18.sp,
                fontWeight = FontWeight.Bold,
                color = TextPrimary,
            )
            Spacer(Modifier.height(6.dp))
            Row(verticalAlignment = Alignment.Bottom) {
                Text(
                    "${kcal.toDoubleOrNull()?.roundToInt() ?: 0}",
                    fontSize = 34.sp,
                    fontWeight = FontWeight.Bold,
                    color = color,
                )
                Spacer(Modifier.width(3.dp))
                Text("千卡", fontSize = 12.sp, color = TextSecondary, modifier = Modifier.padding(bottom = 5.dp))
            }
            Spacer(Modifier.height(6.dp))
            Text(
                sourceLabel(
                    when (selected) {
                        is Selected.Food -> selected.item.source
                        is Selected.Exercise -> selected.item.source
                    }
                ),
                fontSize = 11.sp,
                fontWeight = FontWeight.Medium,
                color = TextSecondary,
                modifier = Modifier
                    .clip(CircleShape)
                    .background(TextSecondary.copy(alpha = 0.08f))
                    .padding(horizontal = 10.dp, vertical = 4.dp),
            )

            Spacer(Modifier.height(18.dp))

            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(18.dp))
                    .background(Card)
                    .padding(horizontal = 18.dp),
            ) {
                if (isFood && origin.grams.isNotEmpty()) {
                    EditRow("克数", grams, { grams = it }, "克", decimal = true)
                }
                if (!isFood) {
                    if (origin.load.isNotEmpty()) EditRow("负重", load, { load = it }, "公斤", decimal = true)
                    if (origin.reps.isNotEmpty()) EditRow("次数", reps, { reps = it }, "次")
                    if (origin.duration.isNotEmpty()) EditRow("时长", duration, { duration = it }, "分钟", decimal = true)
                }
                EditRow("热量", kcal, { kcal = it }, "千卡", decimal = true)

                staticRows(selected).forEach { (label, value) -> StaticRow(label, value) }
            }

            if (kcal != origin.kcal) {
                Text(
                    "直接改热量，会按你报的数记",
                    fontSize = 11.sp,
                    color = TextSecondary,
                    modifier = Modifier.padding(top = 8.dp),
                )
            }

            errorMsg?.let {
                Text(it, fontSize = 12.sp, color = Burn, modifier = Modifier.padding(top = 10.dp))
            }

            if (dirty) {
                Button(
                    onClick = {
                        val patch = buildPatch(origin, grams, load, reps, duration, kcal)
                        if (patch == null) {
                            errorMsg = "数字不对劲：不能为空、零或负数"
                            return@Button
                        }
                        busy = true
                        errorMsg = null
                        scope.launch {
                            runCatching { Api.patchRecord(kind, id, patch) }
                                .fold(
                                    onSuccess = { onChanged(); onDismiss() },
                                    onFailure = {
                                        errorMsg = "保存失败：${it.message}"
                                        busy = false
                                    },
                                )
                        }
                    },
                    enabled = !busy,
                    colors = ButtonDefaults.buttonColors(containerColor = Brand),
                    shape = RoundedCornerShape(16.dp),
                    modifier = Modifier.fillMaxWidth().height(50.dp).padding(top = 0.dp),
                ) {
                    if (busy) {
                        CircularProgressIndicator(Modifier.size(20.dp), Color.White, 2.dp)
                    } else {
                        Text("保存修改", fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
                    }
                }
            }

            Spacer(Modifier.height(if (dirty) 10.dp else 24.dp))

            TextButton(
                onClick = {
                    if (confirmingDelete) {
                        busy = true
                        scope.launch {
                            runCatching { Api.deleteRecord(kind, id) }
                                .fold(
                                    onSuccess = { onChanged(); onDismiss() },
                                    onFailure = {
                                        errorMsg = "删除失败：${it.message}"
                                        busy = false
                                        confirmingDelete = false
                                    },
                                )
                        }
                    } else {
                        confirmingDelete = true
                    }
                },
                enabled = !busy,
            ) {
                Text(
                    if (confirmingDelete) "再点一次确认删除" else "删除这条",
                    fontSize = 14.sp,
                    fontWeight = if (confirmingDelete) FontWeight.SemiBold else FontWeight.Normal,
                    color = if (confirmingDelete) Burn else TextSecondary,
                )
            }
        }
    }
}

private data class Origin(
    val grams: String = "",
    val load: String = "",
    val reps: String = "",
    val duration: String = "",
    val kcal: String = "",
)

/** 只改动过的字段进请求体;任一改动值不是正数就整体作废,由界面报错 */
private fun buildPatch(
    o: Origin,
    grams: String,
    load: String,
    reps: String,
    duration: String,
    kcal: String,
): RecordPatch? {
    var p = RecordPatch()
    if (grams != o.grams) {
        val v = grams.toDoubleOrNull()?.takeIf { it > 0 } ?: return null
        p = p.copy(grams = v)
    }
    if (load != o.load) {
        val v = load.toDoubleOrNull()?.takeIf { it > 0 } ?: return null
        p = p.copy(loadKg = v)
    }
    if (reps != o.reps) {
        val v = reps.toIntOrNull()?.takeIf { it > 0 } ?: return null
        p = p.copy(reps = v)
    }
    if (duration != o.duration) {
        val v = duration.toDoubleOrNull()?.takeIf { it > 0 } ?: return null
        p = p.copy(durationMin = v)
    }
    if (kcal != o.kcal) {
        val v = kcal.toDoubleOrNull()?.takeIf { it > 0 } ?: return null
        p = p.copy(kcal = v)
    }
    return p
}

private fun staticRows(selected: Selected): List<Pair<String, String>> = when (selected) {
    is Selected.Food -> buildList {
        val f = selected.item
        f.protein?.let { add("蛋白质" to "%.1f 克".format(it)) }
        f.fat?.let { add("脂肪" to "%.1f 克".format(it)) }
        f.cho?.let { add("碳水" to "%.1f 克".format(it)) }
        f.fiber?.let { add("膳食纤维" to "%.1f 克".format(it)) }
        if (cleanFoodName(f.foodName) != f.foodName) add("成分表名" to f.foodName)
    }

    is Selected.Exercise -> buildList {
        selected.item.kcalNet?.let { add("净耗" to "${it.roundToInt()} 千卡") }
    }
}

private fun sourceLabel(source: String): String = when (source) {
    "llm_estimated" -> "AI 估算，可改可删"
    "user_reported" -> "你报的数"
    "user_food" -> "你的自定义食物"
    "food_table" -> "查成分表得出"
    "met_table" -> "查运动表算出"
    else -> "已记录"
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun EditRow(
    label: String,
    value: String,
    onChange: (String) -> Unit,
    unit: String,
    decimal: Boolean = false,
) {
    Column {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(label, fontSize = 14.sp, color = TextSecondary)
            Spacer(Modifier.weight(1f))
            TextField(
                value = value,
                onValueChange = onChange,
                singleLine = true,
                textStyle = androidx.compose.ui.text.TextStyle(
                    fontSize = 14.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = Brand,
                    textAlign = TextAlign.End,
                ),
                keyboardOptions = KeyboardOptions(
                    keyboardType = if (decimal) KeyboardType.Decimal else KeyboardType.Number
                ),
                colors = TextFieldDefaults.colors(
                    focusedContainerColor = Color.Transparent,
                    unfocusedContainerColor = Color.Transparent,
                    focusedIndicatorColor = Color.Transparent,
                    unfocusedIndicatorColor = Color.Transparent,
                ),
                modifier = Modifier.width(110.dp),
            )
            Text(unit, fontSize = 12.sp, color = TextSecondary)
        }
        HorizontalDivider(color = TextSecondary.copy(alpha = 0.15f))
    }
}

@Composable
private fun StaticRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(label, fontSize = 14.sp, color = TextSecondary)
        Spacer(Modifier.weight(1f))
        Text(value, fontSize = 14.sp, fontWeight = FontWeight.Medium, color = TextPrimary)
    }
}

/** 整数就不带小数点,免得输入框里出现 200.0 */
private fun Double?.clean(): String = when {
    this == null -> ""
    this == toLong().toDouble() -> toLong().toString()
    else -> "%.1f".format(this)
}
