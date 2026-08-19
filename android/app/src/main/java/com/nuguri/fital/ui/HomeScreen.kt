package com.nuguri.fital.ui

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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
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
import androidx.compose.ui.unit.sp
import com.nuguri.fital.data.Api
import com.nuguri.fital.data.Day
import com.nuguri.fital.data.Dish
import com.nuguri.fital.data.ExerciseItem
import com.nuguri.fital.data.FoodItem
import com.nuguri.fital.data.MealEntry
import com.nuguri.fital.data.cleanFoodName
import com.nuguri.fital.data.display
import com.nuguri.fital.data.isEstimated
import com.nuguri.fital.ui.theme.Brand
import com.nuguri.fital.ui.theme.Burn
import com.nuguri.fital.ui.theme.Card as CardColor
import com.nuguri.fital.ui.theme.Paper
import com.nuguri.fital.ui.theme.TextSecondary
import com.nuguri.fital.ui.theme.Weight
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import kotlin.math.roundToInt

/** 首页每日汇总:只读聚合层,后端已算好合计,前端不做任何算术 */
@Composable
fun HomeScreen(onLoggedOut: () -> Unit) {
    val today = remember { LocalDate.now().toString() }
    var day by remember { mutableStateOf<Day?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }
    var sending by remember { mutableStateOf(false) }
    var statusText by remember { mutableStateOf<String?>(null) }
    var reply by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    suspend fun load() {
        loading = true
        error = null
        runCatching { Api.day(today) }
            .fold(onSuccess = { day = it }, onFailure = { error = it.message ?: "加载失败" })
        loading = false
    }

    LaunchedEffect(Unit) { load() }

    Column(modifier = Modifier.fillMaxSize().background(Paper)) {
        Box(modifier = Modifier.weight(1f)) {
            when {
                loading && day == null -> Box(Modifier.fillMaxSize(), Alignment.Center) {
                    CircularProgressIndicator(color = Brand)
                }

                error != null && day == null -> Column(
                    modifier = Modifier.fillMaxSize().padding(32.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp, Alignment.CenterVertically),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text(error!!, style = MaterialTheme.typography.bodyLarge, color = Burn)
                    TextButton(onClick = { scope.launch { load() } }) { Text("重试") }
                }

                else -> DayContent(
                    day = day!!,
                    onRefresh = { scope.launch { load() } },
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

@Composable
private fun DayContent(day: Day, onRefresh: () -> Unit, onLogout: () -> Unit) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column {
                    Text(
                        dateTitle(day.date),
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.Bold,
                    )
                    Text(
                        day.date,
                        style = MaterialTheme.typography.bodySmall,
                        color = TextSecondary,
                    )
                }
                TextButton(onClick = onLogout) { Text("退出登录") }
            }
        }

        item { SummaryCard(day, onRefresh) }

        if (day.meals.isEmpty() && day.sessions.isEmpty()) {
            item {
                Text(
                    "今天还没有记录",
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextSecondary,
                    modifier = Modifier.fillMaxWidth().padding(top = 40.dp),
                )
            }
        }

        items(day.meals, key = { "meal-${it.id}" }) { group ->
            GroupCard(group.name ?: "用餐", group.start, group.kcalTotal, Brand) {
                group.items.forEach { MealRow(it) }
            }
        }

        items(day.sessions, key = { "session-${it.id}" }) { group ->
            GroupCard(group.name ?: "运动", group.start, group.kcalTotal, Burn) {
                group.items.forEach { ExerciseRow(it) }
            }
        }
    }
}

@Composable
private fun SummaryCard(day: Day, onRefresh: () -> Unit) {
    PaperCard {
        Row(
            modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
            horizontalArrangement = Arrangement.SpaceEvenly,
        ) {
            Stat("摄入", "${day.intakeKcal.roundToInt()}", "千卡", Brand)
            Stat("消耗", "${day.burnKcal.roundToInt()}", "千卡", Burn)
            Stat("体重", day.weight?.let { "%.1f".format(it) } ?: "—", "公斤", Weight)
        }
        day.bmrKcal?.let { bmr ->
            val net = day.intakeKcal - bmr - day.burnNetKcal
            Text(
                "净摄入 ${net.roundToInt()} 千卡（已扣基础代谢 ${bmr.roundToInt()}）",
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary,
                modifier = Modifier.padding(top = 12.dp),
            )
        }
        TextButton(onClick = onRefresh, modifier = Modifier.padding(top = 4.dp)) { Text("刷新") }
    }
}

@Composable
private fun Stat(label: String, value: String, unit: String, color: androidx.compose.ui.graphics.Color) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(label, style = MaterialTheme.typography.bodySmall, color = TextSecondary)
        Spacer(Modifier.height(6.dp))
        Text(value, fontSize = 30.sp, fontWeight = FontWeight.Bold, color = color)
        Text(unit, style = MaterialTheme.typography.bodySmall, color = TextSecondary)
    }
}

@Composable
private fun GroupCard(
    name: String,
    start: String,
    kcalTotal: Double,
    accent: androidx.compose.ui.graphics.Color,
    content: @Composable () -> Unit,
) {
    PaperCard {
        Row(
            modifier = Modifier.fillMaxWidth().padding(bottom = 10.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Text(
                    "  ${clockOf(start)}",
                    style = MaterialTheme.typography.bodySmall,
                    color = TextSecondary,
                )
            }
            Text(
                "${kcalTotal.roundToInt()} 千卡",
                style = MaterialTheme.typography.titleSmall,
                color = accent,
                fontWeight = FontWeight.SemiBold,
            )
        }
        content()
    }
}

@Composable
private fun MealRow(entry: MealEntry) {
    when (entry) {
        is FoodItem -> Line(
            title = cleanFoodName(entry.foodName),
            detail = entry.grams?.let { "${it.roundToInt()} 克" },
            kcal = entry.kcal,
            estimated = entry.source.isEstimated,
        )

        is Dish -> {
            Line(
                title = entry.dishName,
                detail = "${entry.totalGrams.roundToInt()} 克",
                kcal = entry.kcalTotal,
                estimated = false,
                bold = true,
            )
            entry.items.forEach {
                Line(
                    title = "· ${cleanFoodName(it.foodName)}",
                    detail = it.grams?.let { g -> "${g.roundToInt()} 克" },
                    kcal = it.kcal,
                    estimated = it.source.isEstimated,
                    indent = true,
                )
            }
        }
    }
}

@Composable
private fun ExerciseRow(item: ExerciseItem) {
    val detail = listOfNotNull(
        item.durationMin?.let { "${it.roundToInt()} 分钟" },
        item.loadKg?.let { "${it.roundToInt()} 公斤" },
        item.reps?.let { "${it} 次" },
    ).joinToString(" · ").ifBlank { null }

    Line(
        title = item.exerciseName,
        detail = detail,
        kcal = item.kcal,
        estimated = item.source.isEstimated,
    )
}

@Composable
private fun Line(
    title: String,
    detail: String?,
    kcal: Double,
    estimated: Boolean,
    bold: Boolean = false,
    indent: Boolean = false,
) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(start = if (indent) 12.dp else 0.dp, top = 6.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(modifier = Modifier.fillMaxWidth(0.72f)) {
            Text(
                title,
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = if (bold) FontWeight.SemiBold else FontWeight.Normal,
            )
            val sub = listOfNotNull(detail, if (estimated) "AI 估算" else null).joinToString(" · ")
            if (sub.isNotEmpty()) {
                Text(
                    sub,
                    style = MaterialTheme.typography.bodySmall,
                    color = if (estimated) Burn else TextSecondary,
                )
            }
        }
        Text("${kcal.roundToInt()}", style = MaterialTheme.typography.bodyLarge, color = TextSecondary)
    }
}

@Composable
private fun PaperCard(content: @Composable () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = CardColor),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Column(modifier = Modifier.padding(18.dp)) { content() }
    }
}

/** 后端时间戳形态不定(带不带时区、带不带小数秒),两种都收,取本地时钟的时分 */
private fun clockOf(iso: String): String = runCatching {
    OffsetDateTime.parse(iso).atZoneSameInstant(ZoneId.systemDefault()).toLocalTime()
}.recoverCatching {
    LocalDateTime.parse(iso).toLocalTime()
}.getOrNull()?.format(DateTimeFormatter.ofPattern("HH:mm")) ?: ""

private fun dateTitle(date: String): String =
    if (date == LocalDate.now().toString()) "今天" else date
