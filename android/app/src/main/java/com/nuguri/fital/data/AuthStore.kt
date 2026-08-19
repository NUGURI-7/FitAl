package com.nuguri.fital.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.tokenStore by preferencesDataStore(name = "auth")

/**
 * 登录令牌存取:落在应用私有目录,由系统文件级加密与应用沙箱隔离
 * (Jetpack Security 的加密偏好存储已废弃,不再使用)。
 * 契约 2026-07-12:令牌=纯随机不透明串,长期有效;退出登录或被踢即删。
 */
object AuthStore {
    private val KEY = stringPreferencesKey("token")
    private lateinit var appContext: Context

    /** 任一业务请求 401(令牌被删/失效):接口层清令牌后发信号,门卫整界面切回登录页 */
    val unauthorized = MutableSharedFlow<Unit>(extraBufferCapacity = 1)

    fun init(context: Context) {
        appContext = context.applicationContext
    }

    suspend fun token(): String? = appContext.tokenStore.data.map { it[KEY] }.first()

    suspend fun save(token: String) {
        appContext.tokenStore.edit { it[KEY] = token }
    }

    suspend fun clear() {
        appContext.tokenStore.edit { it.remove(KEY) }
    }
}
