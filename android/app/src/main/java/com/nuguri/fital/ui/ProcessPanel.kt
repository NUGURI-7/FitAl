package com.nuguri.fital.ui

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.nuguri.fital.data.ChatStatus
import com.nuguri.fital.ui.theme.Brand
import com.nuguri.fital.ui.theme.Card
import com.nuguri.fital.ui.theme.TextSecondary
import kotlinx.coroutines.delay

private enum class NodeState { Pending, Active, Done }

private data class Node(val label: String, val glyph: NodeGlyph, val state: NodeState)

enum class NodeGlyph { Understand, Diet, Exercise, Remember, Save }

/**
 * 发送后的过程面板:理解 → 按实际路数的饮食 / 运动 / 记住 → 入库,随后端状态事件逐个点亮。
 * 展示节奏与事件到达解耦:事件只决定能不能往前走,每步保底亮一小会儿,
 * 快句子不闪跳;流结束后积压事件快进消化,全亮定格再收。
 */
@Composable
fun ProcessPanel(events: List<ChatStatus>, done: Boolean, onGone: () -> Unit) {
    var applied by remember { mutableIntStateOf(0) }
    var closing by remember { mutableStateOf(false) }

    LaunchedEffect(applied, events.size, done) {
        if (applied < events.size) {
            delay(if (done) 160 else 450)
            applied += 1
            return@LaunchedEffect
        }
        if (done && !closing) {
            delay(480)
            closing = true
            delay(260)
            onGone()
        }
    }

    val nodes = deriveNodes(events.take(applied), finished = done && applied >= events.size)
    if (nodes.isEmpty()) return

    Row(
        modifier = Modifier
            .padding(bottom = 8.dp)
            .alpha(if (closing) 0f else 1f)
            .scale(if (closing) 0.88f else 1f)
            .shadow(6.dp, RoundedCornerShape(22.dp), spotColor = Color.Black.copy(alpha = 0.12f))
            .clip(RoundedCornerShape(22.dp))
            .background(Card)
            .padding(horizontal = 16.dp, vertical = 9.dp),
        verticalAlignment = Alignment.Top,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        nodes.forEachIndexed { i, n ->
            if (i > 0) {
                Box(
                    modifier = Modifier
                        .padding(top = 13.dp)
                        .width(14.dp)
                        .height(2.dp)
                        .clip(CircleShape)
                        .background(
                            if (n.state == NodeState.Pending) TextSecondary.copy(alpha = 0.2f)
                            else Brand.copy(alpha = 0.45f)
                        ),
                )
            }
            NodeView(n)
        }
    }
}

/** 走到入库才算成功:成功收场全节点点亮;整句失败没有入库事件,保持原状收起 */
private fun deriveNodes(events: List<ChatStatus>, finished: Boolean): List<Node> {
    var tracks: List<String>? = null
    val doneTracks = mutableSetOf<String>()
    var saving = false
    events.forEach { e ->
        when (e.stage) {
            "extract" -> tracks = e.tracks ?: emptyList()
            "track_done" -> e.track?.let { doneTracks += it }
            "saving" -> saving = true
        }
    }
    if (events.isEmpty()) return emptyList()

    val out = mutableListOf(
        Node(
            "理解",
            NodeGlyph.Understand,
            if (finished || tracks != null) NodeState.Done else NodeState.Active,
        )
    )
    tracks?.forEach { t ->
        val (label, glyph) = when (t) {
            "eat" -> "饮食" to NodeGlyph.Diet
            "exercise" -> "运动" to NodeGlyph.Exercise
            "remember" -> "记住" to NodeGlyph.Remember
            else -> t to NodeGlyph.Understand
        }
        out += Node(
            label,
            glyph,
            // 各路并发:出现即活跃;入库开始说明各路都已收束
            if (finished || saving || t in doneTracks) NodeState.Done else NodeState.Active,
        )
    }
    if (tracks != null) {
        out += Node(
            "入库",
            NodeGlyph.Save,
            when {
                finished -> NodeState.Done
                saving -> NodeState.Active
                else -> NodeState.Pending
            },
        )
    }
    return out
}

@Composable
private fun NodeView(n: Node) {
    val breathe = rememberInfiniteTransition(label = "breathe")
    val pulse by breathe.animateFloat(
        initialValue = 1f,
        targetValue = 1.12f,
        animationSpec = infiniteRepeatable(tween(700), RepeatMode.Reverse),
        label = "pulse",
    )
    val scale = if (n.state == NodeState.Active) pulse else 1f

    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Box(
            modifier = Modifier
                .scale(scale)
                .size(28.dp)
                .clip(CircleShape)
                .background(
                    when (n.state) {
                        NodeState.Done -> Brand
                        NodeState.Active -> Brand.copy(alpha = 0.14f)
                        NodeState.Pending -> Color.Black.copy(alpha = 0.05f)
                    }
                ),
            contentAlignment = Alignment.Center,
        ) {
            Glyph(
                n.glyph,
                when (n.state) {
                    NodeState.Done -> Color.White
                    NodeState.Active -> Brand
                    NodeState.Pending -> TextSecondary.copy(alpha = 0.5f)
                },
            )
        }
        Spacer(Modifier.height(4.dp))
        Text(
            n.label,
            fontSize = 10.sp,
            fontWeight = if (n.state == NodeState.Pending) FontWeight.Normal else FontWeight.Medium,
            color = if (n.state == NodeState.Pending) TextSecondary.copy(alpha = 0.5f) else TextSecondary,
        )
    }
}

/** 四个小图形自己画,不引整套图标依赖 */
@Composable
private fun Glyph(glyph: NodeGlyph, tint: Color) {
    Canvas(modifier = Modifier.size(13.dp)) {
        val w = size.width
        val h = size.height
        val sw = w * 0.11f
        when (glyph) {
            NodeGlyph.Understand -> {
                // 四角星:理解
                val star = Path().apply {
                    moveTo(w * 0.5f, 0f)
                    cubicTo(w * 0.56f, h * 0.36f, w * 0.64f, h * 0.44f, w, h * 0.5f)
                    cubicTo(w * 0.64f, h * 0.56f, w * 0.56f, h * 0.64f, w * 0.5f, h)
                    cubicTo(w * 0.44f, h * 0.64f, w * 0.36f, h * 0.56f, 0f, h * 0.5f)
                    cubicTo(w * 0.36f, h * 0.44f, w * 0.44f, h * 0.36f, w * 0.5f, 0f)
                    close()
                }
                drawPath(star, tint)
            }

            NodeGlyph.Diet -> {
                listOf(0.18f, 0.32f, 0.46f).forEach {
                    drawLine(tint, Offset(w * it, h * 0.06f), Offset(w * it, h * 0.34f), sw, StrokeCap.Round)
                }
                drawLine(tint, Offset(w * 0.32f, h * 0.34f), Offset(w * 0.32f, h * 0.94f), sw, StrokeCap.Round)
                drawLine(tint, Offset(w * 0.80f, h * 0.06f), Offset(w * 0.80f, h * 0.94f), sw, StrokeCap.Round)
                drawLine(tint, Offset(w * 0.68f, h * 0.18f), Offset(w * 0.80f, h * 0.44f), sw, StrokeCap.Round)
            }

            NodeGlyph.Exercise -> {
                drawLine(tint, Offset(w * 0.30f, h * 0.5f), Offset(w * 0.70f, h * 0.5f), w * 0.10f, StrokeCap.Round)
                listOf(0.20f, 0.80f).forEach {
                    drawLine(tint, Offset(w * it, h * 0.24f), Offset(w * it, h * 0.76f), w * 0.16f, StrokeCap.Round)
                }
            }

            NodeGlyph.Remember -> {
                // 书签
                val mark = Path().apply {
                    moveTo(w * 0.22f, h * 0.06f)
                    lineTo(w * 0.78f, h * 0.06f)
                    lineTo(w * 0.78f, h * 0.94f)
                    lineTo(w * 0.5f, h * 0.66f)
                    lineTo(w * 0.22f, h * 0.94f)
                    close()
                }
                drawPath(mark, tint)
            }

            NodeGlyph.Save -> {
                // 向下入盒
                drawLine(tint, Offset(w * 0.5f, h * 0.06f), Offset(w * 0.5f, h * 0.52f), sw, StrokeCap.Round)
                drawLine(tint, Offset(w * 0.30f, h * 0.34f), Offset(w * 0.5f, h * 0.56f), sw, StrokeCap.Round)
                drawLine(tint, Offset(w * 0.70f, h * 0.34f), Offset(w * 0.5f, h * 0.56f), sw, StrokeCap.Round)
                drawLine(tint, Offset(w * 0.14f, h * 0.78f), Offset(w * 0.86f, h * 0.78f), sw, StrokeCap.Round)
            }
        }
    }
}
