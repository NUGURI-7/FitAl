// FitAl 语音输入 · 前端会话
// 一次长按/开关 = 一条连接:抓麦克风 → 采样处理器转 16k PCM → WS /api/voice
// 转发给后端(后端再对倒豆包),识别文字回来累计显示。只做语音转文字,不碰记录。
// 令牌失效与 HTTP 401 同处理(清令牌回登录页);其余错误抛给调用方提示。

import { forceLogout, getToken } from "@/api";

/** 会话对外状态:连上前=connecting,能说=recording,松手收尾=finishing */
export type VoiceState = "recording" | "finishing";

export interface VoiceHandlers {
  /** 状态推进(connecting 由调用方在点击时自行置,这里只发后续状态) */
  onState: (s: VoiceState) => void;
  /** 本次录音到目前为止的整句(累计全量,覆盖显示) */
  onPartial: (fullText: string) => void;
  /** 当前音量 0..1,驱动声波条 */
  onLevel: (level: number) => void;
  /** 整段结束,给最终整句 */
  onDone: (finalText: string) => void;
  /** 非鉴权类错误(鉴权失效已内部踢回登录页,不走这里) */
  onError: (message: string) => void;
}

export interface VoiceController {
  /** 松手:正常收尾(等后端把尾段识别完再结束) */
  stop: () => void;
  /** 放弃:静默清理(组件卸载等,不出提示、不回填) */
  cancel: () => void;
}

// 采样处理器放 public/,原样作为静态资源提供(不被打包内联,addModule 可 fetch)
const WORKLET_URL = import.meta.env.BASE_URL + "pcmWorklet.js";

function wsUrl(): string {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${location.host}/api/voice`;
}

interface WSMsg {
  type: string;
  text?: string;
  message?: string;
  is_final?: boolean;
}

/** 启动一次语音会话;同步返回控制器,内部异步搭建音频与连接。 */
export function createVoice(h: VoiceHandlers): VoiceController {
  const token = getToken();

  let ws: WebSocket | null = null;
  let ctx: AudioContext | null = null;
  let stream: MediaStream | null = null;
  let node: AudioWorkletNode | null = null;
  let analyser: AnalyserNode | null = null;
  let raf = 0;

  let ready = false; // 后端已回 ready,可以送音频
  let stopRequested = false; // 用户已松手
  let sentStop = false; // 已给后端发过 stop(其后音频一律丢弃)
  let ended = false; // 已彻底收尾
  let lastText = "";
  const preReady: ArrayBuffer[] = []; // ready 之前攒下的音频,ready 后补发

  const cleanup = () => {
    if (ended) return;
    ended = true;
    if (raf) cancelAnimationFrame(raf);
    raf = 0;
    try {
      node?.disconnect();
    } catch {
      /* 忽略 */
    }
    try {
      analyser?.disconnect();
    } catch {
      /* 忽略 */
    }
    stream?.getTracks().forEach((t) => t.stop());
    try {
      void ctx?.close();
    } catch {
      /* 忽略 */
    }
    try {
      ws?.close();
    } catch {
      /* 忽略 */
    }
    h.onLevel(0);
  };

  const fail = (msg: string) => {
    if (ended) return;
    cleanup();
    h.onError(msg);
  };

  // 松手:让处理器把尾包吐出来,收到 flushed 回执后再发 stop
  const beginStop = () => {
    if (sentStop) return;
    if (node) {
      try {
        node.port.postMessage("flush");
        return;
      } catch {
        /* 落到下面直接发 stop */
      }
    }
    sentStop = true;
    try {
      ws?.send(JSON.stringify({ type: "stop" }));
    } catch {
      /* 忽略 */
    }
  };

  void (async () => {
    if (!token) {
      ended = true;
      forceLogout();
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      fail("当前环境不支持麦克风(需在 HTTPS 或 localhost 下打开)");
      return;
    }

    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
    } catch {
      fail("无法使用麦克风,请检查浏览器权限");
      return;
    }
    if (stopRequested) {
      cleanup();
      return;
    }

    try {
      ctx = new AudioContext({ sampleRate: 16000 });
    } catch {
      ctx = new AudioContext(); // 不支持指定采样率的浏览器:处理器内自己重采样
    }
    if (ctx.state === "suspended") {
      try {
        await ctx.resume();
      } catch {
        /* 忽略 */
      }
    }
    try {
      await ctx.audioWorklet.addModule(WORKLET_URL);
    } catch {
      fail("语音组件加载失败");
      return;
    }
    if (stopRequested) {
      cleanup();
      return;
    }

    const src = ctx.createMediaStreamSource(stream);
    analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    src.connect(analyser);

    node = new AudioWorkletNode(ctx, "pcm-downsampler");
    src.connect(node);
    node.connect(ctx.destination); // 输出为静音,仅为驱动处理器的 process()

    node.port.onmessage = (e: MessageEvent) => {
      const d = e.data as unknown;
      if (d instanceof ArrayBuffer) {
        if (sentStop) return;
        if (!ready) {
          preReady.push(d);
          return;
        }
        try {
          ws?.send(d);
        } catch {
          /* 忽略 */
        }
        return;
      }
      // 处理器 flush 完的回执:此刻音频已全部发出,补上 stop
      if (d && typeof d === "object" && (d as { flushed?: boolean }).flushed) {
        if (sentStop) return;
        sentStop = true;
        try {
          ws?.send(JSON.stringify({ type: "stop" }));
        } catch {
          /* 忽略 */
        }
      }
    };

    // 声波:读时域波形算 RMS → 0..1
    const wave = new Uint8Array(analyser.frequencyBinCount);
    const tick = () => {
      if (ended) return;
      analyser!.getByteTimeDomainData(wave);
      let sum = 0;
      for (let i = 0; i < wave.length; i++) {
        const v = (wave[i] - 128) / 128;
        sum += v * v;
      }
      const rms = Math.sqrt(sum / wave.length);
      h.onLevel(Math.min(1, rms * 3.2)); // 经验放大:正常说话接近满格
      raf = requestAnimationFrame(tick);
    };

    ws = new WebSocket(wsUrl());
    ws.binaryType = "arraybuffer";
    ws.onopen = () => {
      try {
        ws!.send(JSON.stringify({ type: "start", token }));
      } catch {
        /* 忽略 */
      }
    };
    ws.onmessage = (ev) => {
      let m: WSMsg;
      try {
        m = JSON.parse(ev.data as string) as WSMsg;
      } catch {
        return;
      }
      if (m.type === "ready") {
        ready = true;
        h.onState("recording");
        raf = requestAnimationFrame(tick);
        for (const b of preReady) {
          try {
            ws!.send(b);
          } catch {
            /* 忽略 */
          }
        }
        preReady.length = 0;
        if (stopRequested) beginStop(); // 连上之前就松手了:补发收尾
      } else if (m.type === "result") {
        lastText = m.text ?? lastText;
        h.onPartial(lastText);
      } else if (m.type === "done") {
        const t = lastText;
        cleanup();
        h.onDone(t);
      } else if (m.type === "error") {
        const msg = typeof m.message === "string" ? m.message : "语音出错";
        if (msg.includes("未登录")) {
          cleanup();
          forceLogout();
        } else {
          fail("语音识别出错:" + msg);
        }
      }
    };
    ws.onerror = () => {
      if (!ended) fail("语音连接失败");
    };
    ws.onclose = () => {
      if (ended) return;
      // 后端未发 done 就断开:有识别结果按结束处理,否则报错
      const t = lastText;
      cleanup();
      if (t) h.onDone(t);
      else h.onError("语音连接已断开");
    };
  })();

  return {
    stop: () => {
      if (ended || stopRequested) return;
      stopRequested = true;
      h.onState("finishing");
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
      h.onLevel(0);
      if (ready) beginStop(); // 未 ready 时,ready 分支里会补发
    },
    cancel: () => cleanup(),
  };
}
