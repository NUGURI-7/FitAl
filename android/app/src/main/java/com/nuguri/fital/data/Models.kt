package com.nuguri.fital.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** 每日汇总(GET /days/{date}):只读聚合层,后端已算好,前端不做算术 */
@Serializable
data class Day(
    val date: String,
    @SerialName("intake_kcal") val intakeKcal: Double = 0.0,
    @SerialName("burn_kcal") val burnKcal: Double = 0.0,
    @SerialName("bmr_kcal") val bmrKcal: Double? = null,
    @SerialName("burn_net_kcal") val burnNetKcal: Double = 0.0,
    val weight: Double? = null,
    val meals: List<MealGroup> = emptyList(),
    val sessions: List<SessionGroup> = emptyList(),
)

/** 餐次(时段制,纯代码归组) */
@Serializable
data class MealGroup(
    val id: Int,
    val name: String? = null,
    val start: String,
    @SerialName("kcal_total") val kcalTotal: Double = 0.0,
    val items: List<MealEntry> = emptyList(),
)

/** 运动场次(AI 判断延续或新开并起名) */
@Serializable
data class SessionGroup(
    val id: Int,
    val name: String? = null,
    val start: String,
    @SerialName("kcal_total") val kcalTotal: Double = 0.0,
    val items: List<ExerciseItem> = emptyList(),
)

/** 餐次明细两种形态:单品 / 菜(成分归拢,合计现算不建表) */
@Serializable
sealed interface MealEntry

@Serializable
@SerialName("food")
data class FoodItem(
    val id: Int = 0,
    @SerialName("food_name") val foodName: String = "",
    val kcal: Double = 0.0,
    val grams: Double? = null,
    val protein: Double? = null,
    val fat: Double? = null,
    val cho: Double? = null,
    val fiber: Double? = null,
    val source: String = "",
) : MealEntry

@Serializable
@SerialName("dish")
data class Dish(
    @SerialName("dish_name") val dishName: String = "",
    @SerialName("total_grams") val totalGrams: Double = 0.0,
    @SerialName("kcal_total") val kcalTotal: Double = 0.0,
    val items: List<FoodItem> = emptyList(),
) : MealEntry

@Serializable
data class ExerciseItem(
    val id: Int = 0,
    @SerialName("exercise_name") val exerciseName: String = "",
    val kcal: Double = 0.0,
    @SerialName("kcal_net") val kcalNet: Double? = null,
    @SerialName("duration_min") val durationMin: Double? = null,
    @SerialName("load_kg") val loadKg: Double? = null,
    val reps: Int? = null,
    val source: String = "",
)

/** 身体档案(GET /users/me):用户名只读不可改,其余可改 */
@Serializable
data class UserProfile(
    val id: Int = 0,
    val username: String? = null,
    val nickname: String = "",
    @SerialName("height_cm") val heightCm: Double = 0.0,
    val sex: String = "male",
    @SerialName("birth_year") val birthYear: Int = 0,
)

/** 改档案请求体:只编码改动了的字段 */
@Serializable
data class UserPatch(
    val nickname: String? = null,
    @SerialName("height_cm") val heightCm: Double? = null,
    val sex: String? = null,
    @SerialName("birth_year") val birthYear: Int? = null,
) {
    val isEmpty: Boolean
        get() = nickname == null && heightCm == null && sex == null && birthYear == null
}

/** 自定义食物:每 100 克口径,与官方表同构 */
@Serializable
data class UserFoodItem(
    val id: Int = 0,
    val name: String = "",
    val form: String? = null,
    val kcal: Double = 0.0,
    @SerialName("updated_at") val updatedAt: String = "",
)

/** AI 记忆:叫法 / 习惯 / 纠正 */
@Serializable
data class MemoryItem(
    val id: Int = 0,
    val kind: String = "",
    val content: String = "",
    @SerialName("updated_at") val updatedAt: String = "",
)

/** 改记录请求体:字段全部可空,只编码改动了的字段 */
@Serializable
data class RecordPatch(
    val grams: Double? = null,
    val kcal: Double? = null,
    @SerialName("duration_min") val durationMin: Double? = null,
    @SerialName("load_kg") val loadKg: Double? = null,
    val reps: Int? = null,
    @SerialName("weight_kg") val weightKg: Double? = null,
)

/** 体重曲线上的一点(GET /weights) */
@Serializable
data class WeightPoint(
    val id: Int = 0,
    @SerialName("weight_kg") val weightKg: Double = 0.0,
    @SerialName("created_at") val createdAt: String = "",
)

/** 数据来源四级:用户自报 / 自定义表 / 查表 / AI 估算。只有估算需要视觉区分 */
val String.isEstimated: Boolean get() = this == "llm_estimated"

/** 来源标签:查表命中不标,其余三种如实标出 */
fun sourceTag(source: String): String? = when (source) {
    "llm_estimated" -> "估算"
    "user_reported" -> "你报的"
    "user_food" -> "自定义"
    else -> null
}

private val JARGON = Regex("""^(代表值|特等|标[一二三四]|[Ff][Aa][Tt]\d+(\.\d+)?[gG])$""")

/**
 * 列表展示名:去掉括号里的成分表编制术语(如"鸡胸脯肉(代表值)"),
 * 括号清空则连括号一起去掉。移植自 Web / iOS,三端同一套规则。
 */
fun cleanFoodName(raw: String): String =
    Regex("""[（(]([^）)]*)[）)]""").replace(raw) { m ->
        val kept = m.groupValues[1]
            .split(',', '，')
            .map(String::trim)
            .filter { it.isNotEmpty() && !JARGON.matches(it) }
        if (kept.isEmpty()) "" else "(" + kept.joinToString("，") + ")"
    }.trim()

/** 对话处理进度(契约 event:status):纯增量,老客户端忽略不坏 */
@Serializable
data class ChatStatus(
    val stage: String = "",
    val tracks: List<String>? = null,
    val track: String? = null,
)

/** 澄清里的一个问题:固定=一句问话 + 数字输入框 + 单位,不做通用表单 */
@Serializable
data class ClarifyQuestion(
    val key: String,
    val prompt: String,
    val unit: String = "",
    val required: Boolean = false,
)

/** 澄清事件(契约 event:clarify):运动段缺数,该段挂在服务器待补 */
@Serializable
data class ChatClarify(
    @SerialName("input_id") val inputId: Int,
    val text: String = "",
    val questions: List<ClarifyQuestion> = emptyList(),
    @SerialName("min_answers") val minAnswers: Int = 1,
)

/** 一次发送的完整结果:模板回执 + 可能的澄清请求 */
data class ChatOutcome(val reply: String, val clarify: ChatClarify? = null)

/** 进度事件转成给用户看的一句话 */
fun ChatStatus.display(): String = when (stage) {
    "triage" -> "正在理解这句话"
    "extract" -> tracks?.takeIf { it.isNotEmpty() }
        ?.let { "正在解析：" + it.joinToString("、") } ?: "正在解析"
    "track_done" -> track?.let { "$it 解析完成" } ?: "解析完成"
    "saving" -> "正在算数入库"
    else -> "处理中"
}
