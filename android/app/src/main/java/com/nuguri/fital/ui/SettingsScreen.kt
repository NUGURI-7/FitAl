package com.nuguri.fital.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
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
import com.nuguri.fital.data.MemoryItem
import com.nuguri.fital.data.UserFoodItem
import com.nuguri.fital.data.UserPatch
import com.nuguri.fital.data.UserProfile
import com.nuguri.fital.ui.theme.Brand
import com.nuguri.fital.ui.theme.Burn
import com.nuguri.fital.ui.theme.Card
import com.nuguri.fital.ui.theme.Paper
import com.nuguri.fital.ui.theme.TextPrimary
import com.nuguri.fital.ui.theme.TextSecondary
import com.nuguri.fital.ui.theme.Weight
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter

/**
 * 设置页:身体档案 + 自定义食物 + AI 记忆 + 退出登录。
 * 档案只发改动字段;改档案不回算已存记录,汇总里现算的数字自动按新档案计。
 */
@Composable
fun SettingsScreen(onBack: () -> Unit, onSaved: () -> Unit, onLoggedOut: () -> Unit) {
    var profile by remember { mutableStateOf<UserProfile?>(null) }
    var foods by remember { mutableStateOf<List<UserFoodItem>>(emptyList()) }
    var memories by remember { mutableStateOf<List<MemoryItem>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }

    var nickname by remember { mutableStateOf("") }
    var height by remember { mutableStateOf("") }
    var sex by remember { mutableStateOf("male") }
    var birthYear by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var toast by remember { mutableStateOf<String?>(null) }
    var armedFood by remember { mutableStateOf<Int?>(null) }
    var armedMemory by remember { mutableStateOf<Int?>(null) }

    val scope = rememberCoroutineScope()
    BackHandler(onBack = onBack)

    LaunchedEffect(Unit) {
        runCatching { Api.me() }.onSuccess {
            profile = it
            nickname = it.nickname
            height = it.heightCm.let { h -> if (h == h.toLong().toDouble()) h.toLong().toString() else "%.1f".format(h) }
            sex = it.sex
            birthYear = it.birthYear.toString()
        }.onFailure { error = it.message }
        foods = runCatching { Api.userFoods() }.getOrDefault(emptyList())
        memories = runCatching { Api.memories() }.getOrDefault(emptyList())
        loading = false
    }

    LaunchedEffect(toast) {
        if (toast != null) {
            delay(2000)
            toast = null
        }
    }
    LaunchedEffect(armedFood) { if (armedFood != null) { delay(3000); armedFood = null } }
    LaunchedEffect(armedMemory) { if (armedMemory != null) { delay(3000); armedMemory = null } }

    val base = profile
    val patch = remember(nickname, height, sex, birthYear, base) {
        if (base == null) UserPatch()
        else UserPatch(
            nickname = nickname.trim().takeIf { it.isNotEmpty() && it != base.nickname },
            heightCm = height.toDoubleOrNull()?.takeIf { it > 0 && it != base.heightCm },
            sex = sex.takeIf { it != base.sex },
            birthYear = birthYear.toIntOrNull()
                ?.takeIf { it in 1900..LocalDate.now().year && it != base.birthYear },
        )
    }

    Box(modifier = Modifier.fillMaxSize().background(Paper)) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .imePadding()
                .padding(horizontal = 16.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                ChevronButton(forward = false, enabled = true, onClick = onBack)
                Spacer(Modifier.width(12.dp))
                Text("设置", fontSize = 20.sp, fontWeight = FontWeight.Bold, color = TextPrimary)
            }

            if (loading) {
                Box(Modifier.fillMaxWidth().padding(vertical = 60.dp), Alignment.Center) {
                    CircularProgressIndicator(color = Brand)
                }
                return@Column
            }

            SectionHeader("身体档案")
            Column(
                modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(Card)
                    .padding(horizontal = 16.dp),
            ) {
                ReadOnlyRow("用户名", base?.username ?: "—")
                FieldRow("昵称", nickname, { nickname = it }, null)
                FieldRow("身高", height, { height = it }, "cm", decimal = true)
                SexRow(sex) { sex = it }
                FieldRow("出生年份", birthYear, { birthYear = it }, "年", numeric = true)
                ReadOnlyRow("用户 ID", base?.id?.toString() ?: "—", last = true)
            }
            Hint(
                "用户名是登录标识，不可改；昵称随便改、可重名。身高、性别、出生年份用于基础代谢与消耗计算；" +
                    "改档案不影响已存的记录，汇总里现算的数字会自动按新档案计。"
            )

            error?.let { Text(it, fontSize = 12.sp, color = Burn, modifier = Modifier.padding(top = 6.dp)) }

            if (!patch.isEmpty) {
                Button(
                    onClick = {
                        busy = true
                        error = null
                        scope.launch {
                            runCatching { Api.patchMe(patch) }.fold(
                                onSuccess = {
                                    profile = runCatching { Api.me() }.getOrNull() ?: profile
                                    toast = "档案已更新"
                                    onSaved()
                                },
                                onFailure = { error = "保存失败：${it.message}" },
                            )
                            busy = false
                        }
                    },
                    enabled = !busy,
                    colors = ButtonDefaults.buttonColors(containerColor = Brand),
                    shape = RoundedCornerShape(16.dp),
                    modifier = Modifier.fillMaxWidth().height(48.dp).padding(top = 0.dp),
                ) {
                    if (busy) CircularProgressIndicator(Modifier.size(18.dp), Color.White, 2.dp)
                    else Text("保存档案", fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
                }
            }

            SectionHeader("自定义食物")
            if (foods.isEmpty()) {
                EmptyLine("还没有自定义食物。对话里说「记住牛肉肠粉一份 300 克 420 千卡」就会记下来。")
            } else {
                Column(
                    modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(Card)
                        .padding(horizontal = 16.dp),
                ) {
                    foods.forEachIndexed { i, f ->
                        ListRow(
                            title = f.name + (f.form?.let { "（$it）" } ?: ""),
                            subtitle = "${f.kcal.toInt()} 千卡 / 100 克 · ${monthDay(f.updatedAt)}",
                            tag = null,
                            armed = armedFood == f.id,
                            onArm = { armedFood = f.id },
                            onConfirm = {
                                scope.launch {
                                    runCatching { Api.deleteUserFood(f.id) }.onSuccess {
                                        foods = foods.filterNot { x -> x.id == f.id }
                                        toast = "已删除"
                                    }
                                    armedFood = null
                                }
                            },
                            last = i == foods.lastIndex,
                        )
                    }
                }
                Hint("删掉只影响以后查表，已经记下的数字不动。")
            }

            SectionHeader("AI 记忆")
            if (memories.isEmpty()) {
                EmptyLine("还没有记忆。纠正过一次之后，它会把你的叫法和习惯记下来。")
            } else {
                Column(
                    modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(Card)
                        .padding(horizontal = 16.dp),
                ) {
                    memories.forEachIndexed { i, m ->
                        ListRow(
                            title = m.content,
                            subtitle = monthDay(m.updatedAt),
                            tag = kindLabel(m.kind) to kindColor(m.kind),
                            armed = armedMemory == m.id,
                            onArm = { armedMemory = m.id },
                            onConfirm = {
                                scope.launch {
                                    runCatching { Api.deleteMemory(m.id) }.onSuccess {
                                        memories = memories.filterNot { x -> x.id == m.id }
                                        toast = "已删除"
                                    }
                                    armedMemory = null
                                }
                            },
                            last = i == memories.lastIndex,
                        )
                    }
                }
                Hint("删掉之后，解析时就不再带上这条。")
            }

            SectionHeader("账号")
            Button(
                onClick = { scope.launch { Api.logout(); onLoggedOut() } },
                colors = ButtonDefaults.buttonColors(
                    containerColor = Card,
                    contentColor = Burn,
                ),
                shape = RoundedCornerShape(16.dp),
                modifier = Modifier.fillMaxWidth().height(48.dp),
            ) {
                Text("退出登录", fontSize = 15.sp, fontWeight = FontWeight.Medium)
            }
            Hint("只下线这台设备，数据都在云端；重新登录即可回来。")

            Spacer(Modifier.height(32.dp))
        }

        toast?.let {
            Box(
                modifier = Modifier.align(Alignment.BottomCenter).padding(bottom = 32.dp)
                    .clip(RoundedCornerShape(20.dp)).background(Card)
                    .padding(horizontal = 16.dp, vertical = 10.dp),
            ) {
                Text(it, fontSize = 13.sp, color = TextPrimary)
            }
        }
    }
}

@Composable
private fun SectionHeader(title: String) {
    Text(
        title,
        fontSize = 13.sp,
        fontWeight = FontWeight.SemiBold,
        color = TextSecondary,
        modifier = Modifier.padding(start = 4.dp, top = 20.dp, bottom = 8.dp),
    )
}

@Composable
private fun Hint(text: String) {
    Text(
        text,
        fontSize = 11.sp,
        color = TextSecondary.copy(alpha = 0.85f),
        modifier = Modifier.padding(start = 4.dp, end = 4.dp, top = 6.dp, bottom = 8.dp),
    )
}

@Composable
private fun EmptyLine(text: String) {
    Box(
        modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(Card)
            .padding(20.dp),
    ) {
        Text(text, fontSize = 12.sp, color = TextSecondary)
    }
}

@Composable
private fun ReadOnlyRow(label: String, value: String, last: Boolean = false) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(label, fontSize = 14.sp, color = TextSecondary)
        Spacer(Modifier.weight(1f))
        Text(value, fontSize = 14.sp, fontWeight = FontWeight.Medium, color = TextPrimary)
    }
    if (!last) HorizontalDivider(color = TextSecondary.copy(alpha = 0.12f))
}

@Composable
private fun FieldRow(
    label: String,
    value: String,
    onChange: (String) -> Unit,
    unit: String?,
    decimal: Boolean = false,
    numeric: Boolean = false,
) {
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
                keyboardType = when {
                    decimal -> KeyboardType.Decimal
                    numeric -> KeyboardType.Number
                    else -> KeyboardType.Text
                }
            ),
            colors = TextFieldDefaults.colors(
                focusedContainerColor = Color.Transparent,
                unfocusedContainerColor = Color.Transparent,
                focusedIndicatorColor = Color.Transparent,
                unfocusedIndicatorColor = Color.Transparent,
            ),
            modifier = Modifier.width(140.dp),
        )
        unit?.let { Text(it, fontSize = 12.sp, color = TextSecondary) }
    }
    HorizontalDivider(color = TextSecondary.copy(alpha = 0.12f))
}

@Composable
private fun SexRow(sex: String, onPick: (String) -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text("性别", fontSize = 14.sp, color = TextSecondary)
        Spacer(Modifier.weight(1f))
        listOf("male" to "男", "female" to "女").forEach { (v, t) ->
            val on = sex == v
            Text(
                t,
                fontSize = 13.sp,
                fontWeight = if (on) FontWeight.SemiBold else FontWeight.Normal,
                color = if (on) Color.White else TextSecondary,
                modifier = Modifier
                    .padding(start = 8.dp)
                    .clip(CircleShape)
                    .background(if (on) Brand else TextSecondary.copy(alpha = 0.08f))
                    .clickableNoRipple { onPick(v) }
                    .padding(horizontal = 16.dp, vertical = 7.dp),
            )
        }
    }
    HorizontalDivider(color = TextSecondary.copy(alpha = 0.12f))
}

@Composable
private fun ListRow(
    title: String,
    subtitle: String,
    tag: Pair<String, Color>?,
    armed: Boolean,
    onArm: () -> Unit,
    onConfirm: () -> Unit,
    last: Boolean,
) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        tag?.let { (label, color) ->
            Text(
                label,
                fontSize = 10.sp,
                fontWeight = FontWeight.Medium,
                color = color,
                modifier = Modifier
                    .clip(CircleShape)
                    .background(color.copy(alpha = 0.12f))
                    .padding(horizontal = 7.dp, vertical = 3.dp),
            )
            Spacer(Modifier.width(8.dp))
        }
        Column(modifier = Modifier.weight(1f)) {
            Text(title, fontSize = 14.sp, color = TextPrimary)
            Text(subtitle, fontSize = 11.sp, color = TextSecondary)
        }
        Spacer(Modifier.width(8.dp))
        if (armed) ConfirmPill(onClick = onConfirm) else TrashButton(onClick = onArm)
    }
    if (!last) HorizontalDivider(color = TextSecondary.copy(alpha = 0.12f))
}

private fun kindLabel(kind: String) = when (kind) {
    "alias" -> "叫法"
    "habit" -> "习惯"
    "correction" -> "纠正"
    else -> kind
}

private fun kindColor(kind: String) = when (kind) {
    "alias" -> Weight
    "habit" -> Brand
    "correction" -> Burn
    else -> TextSecondary
}

private fun monthDay(iso: String): String = runCatching {
    OffsetDateTime.parse(iso).atZoneSameInstant(ZoneId.systemDefault()).toLocalDateTime()
}.recoverCatching { LocalDateTime.parse(iso) }
    .getOrNull()?.format(DateTimeFormatter.ofPattern("M月d日")) ?: ""
