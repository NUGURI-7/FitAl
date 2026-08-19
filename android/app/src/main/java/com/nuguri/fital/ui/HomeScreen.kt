package com.nuguri.fital.ui

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts.RequestPermission
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.clickable
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.SelectableDates
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.nuguri.fital.data.Api
import com.nuguri.fital.data.ChatClarify
import com.nuguri.fital.data.ChatStatus
import androidx.core.content.ContextCompat
import com.nuguri.fital.data.Day
import com.nuguri.fital.data.Dish
import com.nuguri.fital.data.ExerciseItem
import com.nuguri.fital.data.FoodItem
import com.nuguri.fital.data.MealEntry
import com.nuguri.fital.data.VoiceInput
import com.nuguri.fital.data.WeightPoint
import com.nuguri.fital.data.cleanFoodName
import com.nuguri.fital.data.sourceTag
import com.nuguri.fital.ui.theme.Brand
import com.nuguri.fital.ui.theme.Burn
import com.nuguri.fital.ui.theme.TextPrimary
import com.nuguri.fital.ui.theme.TextSecondary
import com.nuguri.fital.ui.theme.Weight
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.temporal.ChronoUnit
import java.time.format.DateTimeFormatter
import kotlin.math.abs
import kotlin.math.roundToInt

/** 首页:只读聚合层,后端已算好合计,前端只做展示口径的换算 */
@Composable
fun HomeScreen(onLoggedOut: () -> Unit) {
    var dayOffset by remember { mutableStateOf(0) }
    var showCalendar by remember { mutableStateOf(false) }
    val shownDate = remember(dayOffset) { LocalDate.now().plusDays(dayOffset.toLong()) }
    var day by remember { mutableStateOf<Day?>(null) }
    var weights by remember { mutableStateOf<List<WeightPoint>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    var appeared by remember { mutableStateOf(false) }
    var sending by remember { mutableStateOf(false) }
    var procEvents by remember { mutableStateOf<List<ChatStatus>>(emptyList()) }
    var procVisible by remember { mutableStateOf(false) }
    var clarify by remember { mutableStateOf<ChatClarify?>(null) }
    var reply by remember { mutableStateOf<String?>(null) }
    var selected by remember { mutableStateOf<Selected?>(null) }
    var showWeights by remember { mutableStateOf(false) }
    var showSettings by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    var draft by remember { mutableStateOf("") }
    val voice = remember { VoiceInput(scope) }
    var voiceBase by remember { mutableStateOf("") }
    val context = LocalContext.current
    val micPermission = rememberLauncherForActivityResult(RequestPermission()) { granted ->
        if (granted) { voiceBase = draft; voice.start() } else reply = "需要麦克风权限才能说话"
    }

    /** 静默刷新:已有数据时失败不清屏,只有首屏失败才进错误态 */
    suspend fun load() {
        runCatching {
            val d = Api.day(shownDate.toString())
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

    // 回执停四秒自动收,与 iOS 同口径;期间来了新回执以新的为准
    LaunchedEffect(reply) {
        if (reply != null) {
            delay(4000)
            reply = null
        }
    }

    LaunchedEffect(voice.transcript) {
        if (voice.transcript.isNotEmpty()) draft = joinVoice(voiceBase, voice.transcript)
    }

    LaunchedEffect(voice.error) {
        voice.error?.let { reply = it; voice.error = null }
    }

    DisposableEffect(Unit) { onDispose { voice.cancel() } }

    LaunchedEffect(dayOffset) {
        day = null
        error = null
        appeared = false
        load()
    }

    if (showSettings) {
        SettingsScreen(
            onBack = { showSettings = false },
            onSaved = { scope.launch { load() } },
            onLoggedOut = onLoggedOut,
        )
        return
    }

    Box(modifier = Modifier.fillMaxSize()) {
        BreathingBackground(brand = Brand, burn = Burn)

        Column(modifier = Modifier.fillMaxSize()) {
            DateBar(
                date = shownDate,
                canGoForward = dayOffset < 0,
                onPrev = { dayOffset -= 1 },
                onNext = { dayOffset += 1 },
                onPick = { showCalendar = true },
            )

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
                        onSelect = { selected = it },
                        onOpenWeights = { showWeights = true },
                        onDeleteDish = { dish ->
                            scope.launch {
                                // 菜不是实体,整删=逐条删成分(raw 是唯一事实源)
                                dish.items.forEach {
                                    runCatching { Api.deleteRecord("food", it.id) }
                                }
                                load()
                            }
                        },
                    )
                }
            }

            ChatBar(
                text = draft,
                onTextChange = { draft = it },
                busy = sending,
                reply = reply,
                recording = voice.isActive,
                level = voice.level,
                onSettings = { showSettings = true },
                onMic = {
                    if (voice.isActive) {
                        voice.stop()
                    } else if (
                        ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO)
                        == PackageManager.PERMISSION_GRANTED
                    ) {
                        voiceBase = draft
                        voice.start()
                    } else {
                        micPermission.launch(Manifest.permission.RECORD_AUDIO)
                    }
                },
                above = {
                    if (procVisible) {
                        ProcessPanel(
                            events = procEvents,
                            done = !sending,
                            onGone = { procVisible = false; procEvents = emptyList() },
                        )
                    }
                    clarify?.let { c ->
                        ClarifyCard(
                            clarify = c,
                            onDone = { text ->
                                clarify = null
                                reply = text
                                scope.launch { load() }
                            },
                            onDismiss = { clarify = null },
                        )
                    }
                },
                onSend = { said ->
                    // 还在录音时点发送:立刻收掉麦克风与语音连接,不让识别结果再回填输入框
                    if (voice.isActive) voice.cancel()
                    sending = true
                    reply = null
                    clarify = null
                    procEvents = emptyList()
                    procVisible = true
                    scope.launch {
                        runCatching { Api.chat(said) { procEvents = procEvents + it } }
                            .fold(
                                onSuccess = { out ->
                                    reply = out.reply
                                    clarify = out.clarify
                                    load()
                                },
                                onFailure = { reply = it.message ?: "发送失败" },
                            )
                        sending = false
                    }
                },
            )
        }

        if (showWeights) {
            WeightSheet(
                weights = weights,
                onDismiss = { showWeights = false },
                onChanged = { scope.launch { load() } },
            )
        }

        selected?.let { sel ->
            RecordSheet(
                selected = sel,
                onDismiss = { selected = null },
                onChanged = { scope.launch { load() } },
            )
        }

        if (showCalendar) {
            DatePickerSheet(
                selected = shownDate,
                onDismiss = { showCalendar = false },
                onPicked = {
                    dayOffset = ChronoUnit.DAYS.between(LocalDate.now(), it).toInt()
                    showCalendar = false
                },
            )
        }
    }
}

/** 顶部日期条:左右翻天,点中间弹月历;不许翻到未来 */
@Composable
private fun DateBar(
    date: LocalDate,
    canGoForward: Boolean,
    onPrev: () -> Unit,
    onNext: () -> Unit,
    onPick: () -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 18.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        ChevronButton(forward = false, enabled = true, onClick = onPrev)
        Column(
            modifier = Modifier.weight(1f).clickable(onClick = onPick),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                dateTitle(date),
                fontSize = 16.sp,
                fontWeight = FontWeight.Bold,
                color = TextPrimary,
            )
            Text(dateSubtitle(date), fontSize = 11.sp, color = TextSecondary)
        }
        ChevronButton(forward = true, enabled = canGoForward, onClick = onNext)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun DatePickerSheet(
    selected: LocalDate,
    onDismiss: () -> Unit,
    onPicked: (LocalDate) -> Unit,
) {
    val todayMillis = LocalDate.now().plusDays(1)
        .atStartOfDay(ZoneId.systemDefault()).toInstant().toEpochMilli()
    val state = rememberDatePickerState(
        initialSelectedDateMillis = selected.atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli(),
        selectableDates = object : SelectableDates {
            override fun isSelectableDate(utcTimeMillis: Long) = utcTimeMillis < todayMillis
        },
    )
    DatePickerDialog(
        onDismissRequest = onDismiss,
        confirmButton = {
            TextButton(onClick = {
                state.selectedDateMillis?.let {
                    onPicked(Instant.ofEpochMilli(it).atZone(ZoneOffset.UTC).toLocalDate())
                } ?: onDismiss()
            }) { Text("好") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    ) {
        DatePicker(state = state, title = null)
    }
}

@Composable
private fun DayContent(
    day: Day,
    weights: List<WeightPoint>,
    appeared: Boolean,
    onSelect: (Selected) -> Unit,
    onOpenWeights: () -> Unit,
    onDeleteDish: (Dish) -> Unit,
) {
    val metrics = remember(day, weights) { Metrics.of(day, weights) }
    val expanded = remember(day.date) { mutableStateListOf<String>() }
    var armedDish by remember(day.date) { mutableStateOf<String?>(null) }

    LaunchedEffect(armedDish) {
        if (armedDish != null) {
            delay(3000)
            armedDish = null
        }
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(start = 18.dp, end = 18.dp, top = 12.dp, bottom = 20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
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
                    modifier = Modifier.weight(1f).fillMaxHeight().clickable(onClick = onOpenWeights),
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
                        meal.items.forEach { entry ->
                            MealRows(
                                entry = entry,
                                expanded = expanded,
                                armedDish = armedDish,
                                onArmDish = { armedDish = it },
                                onSelect = onSelect,
                                onDeleteDish = onDeleteDish,
                            )
                        }
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
                        session.items.forEach { item ->
                            ItemRow(
                                name = item.exerciseName,
                                detail = exerciseDetail(item),
                                kcal = item.kcal.roundToInt(),
                                color = Burn,
                                onClick = { onSelect(Selected.Exercise(item)) },
                            )
                        }
                    }
                }
            }
        }

        if (day.meals.isEmpty() && day.sessions.isEmpty()) {
            item {
                EmptyCard(
                    isToday = day.date == LocalDate.now().toString(),
                    brand = Brand,
                    modifier = Modifier.entrance(appeared, 1),
                )
            }
        }

        if (day.meals.isNotEmpty() || day.sessions.isNotEmpty()) {
            item {
                Text(
                    "点明细可改可删 · 菜行可展开成分",
                    fontSize = 11.sp,
                    color = TextSecondary.copy(alpha = 0.7f),
                    modifier = Modifier.fillMaxWidth(),
                    textAlign = TextAlign.Center,
                )
            }
        }

        item { Spacer(modifier = Modifier.height(44.dp)) }
    }
}

@Composable
private fun MealRows(
    entry: MealEntry,
    expanded: MutableList<String>,
    armedDish: String?,
    onArmDish: (String?) -> Unit,
    onSelect: (Selected) -> Unit,
    onDeleteDish: (Dish) -> Unit,
) {
    when (entry) {
        is FoodItem -> ItemRow(
            name = cleanFoodName(entry.foodName),
            detail = foodDetail(entry),
            kcal = entry.kcal.roundToInt(),
            color = Brand,
            onClick = { onSelect(Selected.Food(entry)) },
        )

        is Dish -> {
            val key = "${entry.dishName}-${entry.items.firstOrNull()?.id ?: 0}"
            val isOpen = key in expanded

            ItemRow(
                name = entry.dishName,
                detail = "${entry.totalGrams.roundToInt()} 克 · ${entry.items.size} 成分",
                kcal = entry.kcalTotal.roundToInt(),
                color = Brand,
                bold = true,
                onClick = { if (isOpen) expanded.remove(key) else expanded.add(key) },
                trailing = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        ExpandChevron(isOpen)
                        if (armedDish == key) {
                            ConfirmPill(onClick = { onArmDish(null); onDeleteDish(entry) })
                        } else {
                            TrashButton(onClick = { onArmDish(key) })
                        }
                    }
                },
            )

            AnimatedVisibility(visible = isOpen) {
                Column {
                    entry.items.forEach { f ->
                        ItemRow(
                            name = cleanFoodName(f.foodName),
                            detail = foodDetail(f),
                            kcal = f.kcal.roundToInt(),
                            color = Brand,
                            indent = true,
                            onClick = { onSelect(Selected.Food(f)) },
                        )
                    }
                }
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

/** 语音文字累加拼接:已有内容非空时,去掉尾部空白再空一格接上 */
private fun joinVoice(base: String, spoken: String): String = when {
    spoken.isEmpty() -> base
    base.isEmpty() -> spoken
    else -> base.trimEnd() + " " + spoken
}

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

/** 标题:今天 / 昨天 / 前天 / 8月16日 */
private fun dateTitle(date: LocalDate): String =
    when (ChronoUnit.DAYS.between(date, LocalDate.now())) {
        0L -> "今天"
        1L -> "昨天"
        2L -> "前天"
        else -> "${date.monthValue}月${date.dayOfMonth}日"
    }

/** 副标题:7月13日 周一 */
private fun dateSubtitle(date: LocalDate): String {
    val week = listOf("周一", "周二", "周三", "周四", "周五", "周六", "周日")[date.dayOfWeek.value - 1]
    return "${date.monthValue}月${date.dayOfMonth}日 $week"
}

/** 后端时间戳形态不定(带不带时区、带不带小数秒),两种都收,统一换算到本地时钟 */
private fun instantOf(iso: String): LocalDateTime? = runCatching {
    OffsetDateTime.parse(iso).atZoneSameInstant(ZoneId.systemDefault()).toLocalDateTime()
}.recoverCatching { LocalDateTime.parse(iso) }.getOrNull()
