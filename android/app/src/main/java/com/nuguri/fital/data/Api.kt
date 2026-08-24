package com.nuguri.fital.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

/** 后端回的业务错误,界面直接把 message 显示给用户 */
class ApiException(message: String) : Exception(message)

/**
 * 后端接口层:契约与 Web / iOS 端完全一致,后端零改动。
 * 三端同指一个地址,换地址只改这一处。
 */
object Api {
    private const val BASE = "https://fital.nuguri.org"
    private val JSON_TYPE = "application/json".toMediaType()

    /** 10 秒连不上就报错,绝不无限等(与 iOS 同口径,假死的根源) */
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .build()

    // explicitNulls = false:改记录只发改动了的字段,没改的不出现在请求体里
    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true; explicitNulls = false }

    /** 对话是流式长响应,读超时另放宽到两分钟;探活/汇总等读接口仍是 10 秒 */
    private val streamClient = client.newBuilder()
        .readTimeout(120, TimeUnit.SECONDS)
        .build()

    @Serializable private data class AuthResponse(val token: String)
    @Serializable private data class ErrorDetail(val detail: String)
    @Serializable private data class LoginIn(val username: String, val password: String)
    @Serializable private data class ChatIn(val text: String)
    @Serializable private data class ReplyData(val text: String)
    @Serializable private data class ClarifyIn(val answers: Map<String, Double>)
    @Serializable private data class ClarifyOut(val reply: String = "已记录")

    @Serializable
    private data class RegisterIn(
        @SerialName("invite_code") val inviteCode: String,
        val username: String,
        val nickname: String?,
        val password: String,
        @SerialName("height_cm") val heightCm: Double,
        val sex: String,
        @SerialName("birth_year") val birthYear: Int,
    )

    /**
     * 统一发请求:自动带上本地令牌。
     * 401 守卫(契约 2026-07-12 第二道):清本地令牌并发信号,门卫整界面切回登录页;
     * 登录/注册自身的 401 是业务错误(密码不对),传 kickOn401 = false 豁免。
     */
    private suspend fun call(
        path: String,
        method: String = "GET",
        body: String? = null,
        kickOn401: Boolean = true,
    ): String = withContext(Dispatchers.IO) {
        val req = Request.Builder().url("$BASE/$path").apply {
            AuthStore.token()?.let { header("Authorization", "Bearer $it") }
            when {
                body != null -> method(method, body.toRequestBody(JSON_TYPE))
                method != "GET" -> method(method, ByteArray(0).toRequestBody(null))
            }
        }.build()

        client.newCall(req).execute().use { resp ->
            val text = resp.body?.string().orEmpty()
            if (resp.isSuccessful) return@withContext text

            if (resp.code == 401 && kickOn401) {
                AuthStore.clear()
                AuthStore.unauthorized.tryEmit(Unit)
                throw ApiException("登录已失效,请重新登录")
            }
            throw ApiException(
                runCatching { json.decodeFromString<ErrorDetail>(text).detail }
                    .getOrElse { "请求失败(${resp.code})" }
            )
        }
    }

    /** 探活:原样返回后端响应体 */
    suspend fun health(): String = call("health")

    /** 登录:用户名+密码;成功即把令牌收进本地,失败后端统一回"用户名或密码不对" */
    suspend fun login(username: String, password: String) {
        val text = call("auth/login", "POST", json.encodeToString(LoginIn(username, password)), false)
        AuthStore.save(json.decodeFromString<AuthResponse>(text).token)
    }

    /** 注册:邀请码+用户名+昵称(空=用用户名)+密码+身体档案;成功当场发令牌,免二次登录 */
    suspend fun register(
        inviteCode: String,
        username: String,
        nickname: String?,
        password: String,
        heightCm: Double,
        sex: String,
        birthYear: Int,
    ) {
        val payload = json.encodeToString(
            RegisterIn(inviteCode, username, nickname, password, heightCm, sex, birthYear)
        )
        val text = call("auth/register", "POST", payload, false)
        AuthStore.save(json.decodeFromString<AuthResponse>(text).token)
    }

    @Serializable private data class WeightsResponse(val weights: List<WeightPoint> = emptyList())

    /** 体重曲线:默认三十天,按时间升序 */
    suspend fun weights(days: Int = 30): List<WeightPoint> =
        json.decodeFromString<WeightsResponse>(call("weights?days=$days")).weights

    /** 每日汇总:只读聚合层,零 AI 调用;date 形如 2026-08-19 */
    suspend fun day(date: String): Day = json.decodeFromString(call("days/$date"))

    /**
     * 发一句话记录(契约:唯一对话入口,SSE 流式)。
     * 边处理边推进度事件,处理完推一句模板回执;进度事件回调切回主线程再交给界面。
     * 记录卡片事件此处不消费——入库完直接重取当天汇总,以聚合层为准。
     */
    suspend fun chat(text: String, onStatus: suspend (ChatStatus) -> Unit): ChatOutcome =
        withContext(Dispatchers.IO) {
            val req = Request.Builder().url("$BASE/chat")
                .apply { AuthStore.token()?.let { header("Authorization", "Bearer $it") } }
                .post(json.encodeToString(ChatIn(text)).toRequestBody(JSON_TYPE))
                .build()

            streamClient.newCall(req).execute().use { resp ->
                if (resp.code == 401) {
                    AuthStore.clear()
                    AuthStore.unauthorized.tryEmit(Unit)
                    throw ApiException("登录已失效,请重新登录")
                }
                if (!resp.isSuccessful) throw ApiException("发送失败(${resp.code})")

                val source = resp.body?.source() ?: throw ApiException("没有响应内容")
                var event = ""
                var reply = ""
                var clarify: ChatClarify? = null
                while (true) {
                    val line = source.readUtf8Line() ?: break
                    when {
                        line.startsWith("event:") -> event = line.removePrefix("event:").trim()
                        line.startsWith("data:") -> {
                            val payload = line.removePrefix("data:").trim()
                            if (payload.isEmpty()) continue
                            when (event) {
                                "reply" -> runCatching {
                                    json.decodeFromString<ReplyData>(payload).text
                                }.getOrNull()?.let { reply = it }

                                "status" -> runCatching {
                                    json.decodeFromString<ChatStatus>(payload)
                                }.getOrNull()?.let { withContext(Dispatchers.Main) { onStatus(it) } }

                                "clarify" -> runCatching {
                                    json.decodeFromString<ChatClarify>(payload)
                                }.getOrNull()?.let { clarify = it }
                            }
                        }
                    }
                }
                ChatOutcome(reply.ifBlank { "已记录" }, clarify)
            }
        }

    /**
     * 澄清补交:答案填进服务器上的待补行,重跑同套纯代码校验后入库,零 AI 二次调用。
     * 已补过或不在待补态回 409,界面按"这条已经处理过了"收起。
     */
    suspend fun submitClarify(inputId: Int, answers: Map<String, Double>): String {
        val text = call("inputs/$inputId/clarify", "POST", json.encodeToString(ClarifyIn(answers)))
        return runCatching { json.decodeFromString<ClarifyOut>(text).reply }.getOrDefault("已记录")
    }

    /**
     * 改记录:只发改动的字段。
     * 改输入量后端按规矩重算热量;直接改热量则采用用户报的数,来源转"你报的"。
     * kind 取 food 或 exercise。
     */
    suspend fun patchRecord(kind: String, id: Int, patch: RecordPatch) {
        call("records/$kind/$id", "PATCH", json.encodeToString(patch))
    }

    /** 删记录:只落 raw,所在餐次或场次由后端增量重算 */
    suspend fun deleteRecord(kind: String, id: Int) {
        call("records/$kind/$id", "DELETE")
    }

    @Serializable private data class UserFoodsResponse(val foods: List<UserFoodItem> = emptyList())
    @Serializable private data class MemoriesResponse(val memories: List<MemoryItem> = emptyList())

    /** 身体档案:读 */
    suspend fun me(): UserProfile = json.decodeFromString(call("users/me"))

    /** 身体档案:改。只发改动字段;改档案不回算已存记录,读时现算的数字自动按新档案计 */
    suspend fun patchMe(patch: UserPatch) {
        call("users/me", "PATCH", json.encodeToString(patch))
    }

    /** 自定义食物列表(按更新时间倒序) */
    suspend fun userFoods(): List<UserFoodItem> =
        json.decodeFromString<UserFoodsResponse>(call("user-foods")).foods

    /** 删自定义食物:只影响以后查表,已存记录的数字不动 */
    suspend fun deleteUserFood(id: Int) {
        call("user-foods/$id", "DELETE")
    }

    /** AI 记忆列表 */
    suspend fun memories(): List<MemoryItem> =
        json.decodeFromString<MemoriesResponse>(call("memories")).memories

    /** 删记忆:即停止注入解析提示词 */
    suspend fun deleteMemory(id: Int) {
        call("memories/$id", "DELETE")
    }

    /**
     * 改密码:旧密码即身份证明。改完服务器把该用户其他设备的令牌全删掉,
     * 当前这台保留;返回被踢下线的设备数。这里的 401 是令牌失效(密码不对回 403),
     * 故照常触发踢回登录页。
     */
    suspend fun changePassword(oldPassword: String, newPassword: String): Int {
        val payload = json.encodeToString(PasswordChangeIn(oldPassword, newPassword))
        val text = call("auth/password", "POST", payload)
        return json.decodeFromString<PasswordChangeOut>(text).revokedDevices
    }

    /** 退出登录:服务器删本枚令牌(幂等);服务器不可达也照样清本地 */
    suspend fun logout() {
        runCatching { call("auth/logout", "POST", kickOn401 = false) }
        AuthStore.clear()
    }
}
