package com.nuguri.fital.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.TimeUnit

/**
 * 后端接口层:契约与 Web / iOS 端完全一致,后端零改动。
 * 三端同指一个地址,换地址只改这一处。
 */
object Api {
    private const val BASE = "https://fital.nuguri.org"

    /** 10 秒连不上就报错,绝不无限等(与 iOS 同口径,假死的根源) */
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .build()

    /** 探活:原样返回后端响应体 */
    suspend fun health(): String = withContext(Dispatchers.IO) {
        val req = Request.Builder().url("$BASE/health").build()
        client.newCall(req).execute().use { resp ->
            val body = resp.body?.string().orEmpty()
            check(resp.isSuccessful) { "HTTP ${resp.code}: $body" }
            body
        }
    }
}
