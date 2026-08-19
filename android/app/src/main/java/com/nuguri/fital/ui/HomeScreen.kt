package com.nuguri.fital.ui

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.nuguri.fital.data.Api
import com.nuguri.fital.data.Day
import com.nuguri.fital.data.Dish
import com.nuguri.fital.data.ExerciseItem
import com.nuguri.fital.data.FoodItem
import com.nuguri.fital.data.MealEntry
import com.nuguri.fital.data.WeightPoint
import com.nuguri.fital.data.cleanFoodName
import com.nuguri.fital.data.display
import com.nuguri.fital.data.sourceTag
import com.nuguri.fital.ui.theme.Brand
import com.nuguri.fital.ui.theme.Burn
import com.nuguri.fital.ui.theme.TextPrimary
import com.nuguri.fital.ui.theme.TextSecondary
import com.nuguri.fital.ui.theme.Weight
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import kotlin.math.abs
import kotlin.math.roundToInt

/** 首页:只读聚合层,后端已算好合计,前端只做展示口径的换算 */
@Composable
fun HomeScreen(onLoggedOut: () -> Unit) {
    val today = remember { LocalDate.now().toString() }
    var day by remember { mutableStateOf<Day?>(null) }
    var weights by remember { mutableStateOf<List<WeightPoint>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    var appeared by remember { mutableStateOf(false) }
    var sending by remember { mutableStateOf(false) }
    var statusText by remember { mutableStateOf<String?>(null) }
    var reply by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    /** 静默刷新:已有数据时失败不清屏,只有首屏失败才进错误态 */
    suspend fun load() {
        runCatching {
            val d = Api.day(today)
            val w = runCatching { Api.weights() }.getOrDefault(emptyList())
            d to w
        }.fold(
            onSuccess = { (d, w) ->
                day = d
                weights = w
                error = null
                appeared = true
            },
            onFailure = { if (day == null) error = it.message ?: "加载失败" },
        )
    }

    LaunchedEffect(Unit) { load() }

    Box(modifier = Modifier.fillMaxSize()) {
        BreathingBackground(brand = Brand, burn = Burn)

        Column(modifier = Modifier.fillMaxSize()) {
            Box(modifier = Modifier.weight(1f)) {
                when {
                    day == null && error == null ->
                        Box(Modifier.fillMaxSize(), Alignment.Center) {
                            CircularProgressIndicator(color = Brand)
                        }

                    day == null ->
                        Column(
                            modifier = Modifier.fillMaxSize().padding(32.dp),
                            verticalArrangement = Arrangement.spacedBy(12.dp, Alignment.CenterVertically),
                            horizontalAlignment = Alignment.CenterHorizontally,
                        ) {
                            Text(error!!, style = MaterialTheme.typography.bodyLarge, color = Burn)
                            TextButton(onClick = { scope.launch { load() } }) { Text("重试") }
                        }

                    else -> DayContent(
                        day = day!!,
                        weights = weights,
                        appeared = appeared,
                        onLogout = { scope.launch { Api.logout(); onLoggedOut() } },
                    )
                }
            }

            ChatBar(
                busy = sending,
                status = statusText,
                reply = reply,
                onSend = { said ->
                    sending = true
                    statusText = null
                    reply = null
                    scope.launch {
                        runCatching { Api.chat(said) { statusText = it.display() } }
                            .fold(
                                onSuccess = { reply = it; load() },
                                onFailure = { reply = it.message ?: "发送失败" },
                            )
                        sending = false
                        statusText = null
                    }
                },
            )
        }
    }
}

@Composable
private fun DayContent(
    day: Day,
    weights: List<WeightPoint>,
    appeared: Boolean,
    onLogout: () -> Unit,
) {
    val metrics = remember(day, weights) { Metrics.of(day, weights) }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(start = 18.dp, end = 18.dp, top = 12.dp, bottom = 20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column {
                    Text(
                        if (day.date == LocalDate.now().toString()) "今天" else day.date,
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.Bold,
                        color = TextPrimary,
                    )
                    Text(dateSubtitle(day.date), style = MaterialTheme.typography.bodySmall, color = TextSecondary)
                }
                TextButton(onClick = onLogout) { Text("退出登录") }
            }
        }

        item {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(IntrinsicSize.Min)
                    .entrance(appeared, 0),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                StatTile(
                    title = if (metrics.isDeficit) "净消耗" else "净摄入",
                    value = animatedInt(metrics.net),
                    unit = "千卡",
                    sub = "",
                    color = if (metrics.isDeficit) Burn else Brand,
                    modifier = Modifier.weight(1f).fillMaxHeight(),
                    gradientNumber = true,
                )
                StatTile(
                    title = "消耗",
                    value = animatedInt(metrics.burnTotal),
                    unit = "千卡",
                    sub = "基础代谢+运动",
                    color = Burn,
                    modifier = Modifier.weight(1f).fillMaxHeight(),
                    accessory = { ProgressRing(metrics.ringProgress, Burn) },
                )
                StatTile(
                    title = "体重",
                    value = metrics.weight?.let { "%.1f".format(it) } ?: "–",
                    unit = "kg",
                    sub = metrics.weightSub,
                    color = Weight,
                    modifier = Modifier.weight(1f).fillMaxHeight(),
                    accessory = { Sparkline(weights.map { it.weightKg }, Weight) },
                )
            }
        }

        if (day.meals.isNotEmpty()) {
            item {
                SectionCard(
                    title = "饮食",
                    totalKcal = day.intakeKcal.roundToInt(),
                    color = Brand,
                    icon = SectionIcon.Diet,
                    modifier = Modifier.entrance(appeared, 1),
                ) {
                    day.meals.forEach { meal ->
                        GroupHeader(
                            name = meal.name ?: "一顿饭",
                            count = meal.items.sumOf { if (it is Dish) it.items.size else 1 },
                            kcal = meal.kcalTotal.roundToInt(),
                        )
                        meal.items.forEach { MealRows(it) }
                    }
                }
            }
        }

        if (day.sessions.isNotEmpty()) {
            item {
                SectionCard(
                    title = "运动",
                    totalKcal = day.burnKcal.roundToInt(),
                    color = Burn,
                    icon = SectionIcon.Exercise,
                    modifier = Modifier.entrance(appeared, 2),
                ) {
                    day.sessions.forEach { session ->
                        GroupHeader(
                            name = session.name ?: "一场训练",
                            count = session.items.size,
                            kcal = session.kcalTotal.roundToInt(),
                        )
                        session.items.forEach {
                            ItemRow(it.exerciseName, exerciseDetail(it), it.kcal.roundToInt(), Burn)
                        }
                    }
                }
            }
        }

        if (day.meals.isEmpty() && day.sessions.isEmpty()) {
            item { EmptyHint("今天还没有记录，在下面说一句就行") }
        }
    }
}

@Composable
private fun MealRows(entry: MealEntry) {
    when (entry) {
        is FoodItem -> ItemRow(
            name = cleanFoodName(entry.foodName),
            detail = foodDetail(entry),
            kcal = entry.kcal.roundToInt(),
            color = Brand,
        )

        is Dish -> {
            ItemRow(
                name = entry.dishName,
                detail = "${entry.totalGrams.roundToInt()} 克 · ${entry.items.size} 样",
                kcal = entry.kcalTotal.roundToInt(),
                color = Brand,
                bold = true,
            )
            entry.items.forEach {
                ItemRow(
                    name = cleanFoodName(it.foodName),
                    detail = foodDetail(it),
                    kcal = it.kcal.roundToInt(),
                    color = Brand,
                    indent = true,
                )
            }
        }
    }
}

private fun foodDetail(f: FoodItem): String = listOfNotNull(
    f.grams?.let { "${it.roundToInt()} 克" },
    sourceTag(f.source),
).joinToString(" · ")

private fun exerciseDetail(e: ExerciseItem): String = listOfNotNull(
    when {
        e.loadKg != null && e.reps != null -> "${e.loadKg.roundToInt()}kg × ${e.reps}"
        e.reps != null -> "× ${e.reps} 次"
        else -> null
    },
    e.durationMin?.let { "%.1f 分钟".format(it) },
    sourceTag(e.source),
).joinToString(" · ").ifBlank { "—" }

/** 数字过渡:变化时滚动到新值,不硬跳 */
@Composable
private fun animatedInt(target: Double): String {
    val v by animateFloatAsState(target.toFloat(), tween(900), label = "num")
    return "%,d".format(v.roundToInt())
}

/**
 * 展示口径(与 Web / iOS 完全一致):
 * 消耗 = 基础代谢按当日已过时间折算 + 运动净耗;净额 = 摄入 − 消耗,为负按"净消耗"显示。
 */
private data class Metrics(
    val net: Double,
    val isDeficit: Boolean,
    val burnTotal: Double,
    val ringProgress: Float,
    val weight: Double?,
    val weightSub: String,
) {
    companion object {
        fun of(day: Day, weights: List<WeightPoint>): Metrics {
            val isToday = day.date == LocalDate.now().toString()
            val frac = if (isToday) {
                (LocalTime.now().toSecondOfDay() / 86_400.0).coerceIn(0.0, 1.0)
            } else 1.0

            val bmr = day.bmrKcal
            val burnTotal = bmr?.let { it * frac + day.burnNetKcal } ?: day.burnKcal
            val net = bmr?.let { day.intakeKcal - burnTotal } ?: 0.0

            val dayStart = LocalDate.parse(day.date).atStartOfDay()
            val prev = weights.lastOrNull { instantOf(it.createdAt)?.isBefore(dayStart) == true }
            val shown = day.weight ?: prev?.weightKg

            val sub = when {
                day.weight != null && prev != null ->
                    "%+.1f 较上次".format(day.weight - prev.weightKg)

                day.weight == null && prev != null ->
                    "上次 " + instantOf(prev.createdAt)?.format(DateTimeFormatter.ofPattern("M/d")).orEmpty()

                else -> ""
            }

            return Metrics(
                net = abs(net),
                isDeficit = net < 0,
                burnTotal = burnTotal,
                ringProgress = if (bmr != null && bmr > 0) (burnTotal / bmr).toFloat().coerceIn(0f, 1f) else 0f,
                weight = shown,
                weightSub = sub,
            )
        }
    }
}

/** 副标题:7月13日 周一 */
private fun dateSubtitle(date: String): String {
    val d = runCatching { LocalDate.parse(date) }.getOrNull() ?: return date
    val week = listOf("周一", "周二", "周三", "周四", "周五", "周六", "周日")[d.dayOfWeek.value - 1]
    return "${d.monthValue}月${d.dayOfMonth}日 $week"
}

/** 后端时间戳形态不定(带不带时区、带不带小数秒),两种都收,统一换算到本地时钟 */
private fun instantOf(iso: String): LocalDateTime? = runCatching {
    OffsetDateTime.parse(iso).atZoneSameInstant(ZoneId.systemDefault()).toLocalDateTime()
}.recoverCatching { LocalDateTime.parse(iso) }.getOrNull()
