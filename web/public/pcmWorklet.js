// FitAl 语音输入 · 麦克风原始采样处理器
// AudioWorklet 独立作用域(自包含,不 import):把麦克风采样重采样到 16k、
// 转 16 位有符号 PCM、按约 200ms 攒成一包回主线程,再由主线程转发给后端。
// 加载:new URL('./pcmWorklet.js', import.meta.url) → audioWorklet.addModule
/* eslint-disable */
/* global AudioWorkletProcessor, registerProcessor, sampleRate */

class PCMDownsampler extends AudioWorkletProcessor {
  constructor() {
    super();
    this._target = 16000;
    this._ratio = sampleRate / this._target; // 输入帧/输出帧;上下文本就 16k 时=1
    this._buf = new Float32Array(0); // 尚未消费的输入样本(跨块承接)
    this._frac = 0; // 下一输出样本在 _buf 中的浮点读取位
    this._batch = []; // 攒够 ~200ms 再发,减少碎包
    this._target200 = Math.round(this._target * 0.2); // 3200
    this.port.onmessage = (e) => {
      if (e.data === "flush") {
        this._flush(true); // 松手:把不足一包的尾巴也吐出去
        this.port.postMessage({ flushed: true }); // 通知主线程:音频已发完,可发 stop
      }
    };
  }

  _flush(force) {
    if (this._batch.length === 0) return;
    if (!force && this._batch.length < this._target200) return;
    const pcm = new Int16Array(this._batch);
    this._batch = [];
    this.port.postMessage(pcm.buffer, [pcm.buffer]);
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;
    const ch = input[0];

    // 上一块的尾巴 + 本块,拼成连续序列做线性重采样
    const merged = new Float32Array(this._buf.length + ch.length);
    merged.set(this._buf, 0);
    merged.set(ch, this._buf.length);

    const ratio = this._ratio;
    let p = this._frac;
    while (Math.floor(p) + 1 < merged.length) {
      const i = Math.floor(p);
      const t = p - i;
      let s = merged[i] * (1 - t) + merged[i + 1] * t;
      if (s > 1) s = 1;
      else if (s < -1) s = -1;
      this._batch.push(s < 0 ? (s * 0x8000) | 0 : (s * 0x7fff) | 0);
      p += ratio;
    }
    const keep = Math.floor(p); // 保留 merged[keep] 起,供下一块首个插值取左邻
    this._buf = merged.slice(keep);
    this._frac = p - keep;

    this._flush(false);
    return true;
  }
}

registerProcessor("pcm-downsampler", PCMDownsampler);
