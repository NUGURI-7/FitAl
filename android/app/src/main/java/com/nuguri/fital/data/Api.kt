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

    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }

    @Serializable private data class AuthResponse(val token: String)
    @Serializable private data class ErrorDetail(val detail: String)
    @Serializable private data class LoginIn(val username: String, val password: String)

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

    /** 退出登录:服务器删本枚令牌(幂等);服务器不可达也照样清本地 */
    suspend fun logout() {
        runCatching { call("auth/logout", "POST", kickOn401 = false) }
        AuthStore.clear()
    }
}
