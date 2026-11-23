"""语音链路自检脚本（不依赖后端服务，直接验证「Key + 网络 + 端点」）。

用法（在 triggerServer 目录下）：
    .venv\\Scripts\\python.exe check_asr.py

它会：
1. 读 .env 里的 ASR 配置
2. 强制 IPv4、绕过系统代理（国内端点走代理经常被拦成 403）
3. 生成一段 3 秒测试音频，直接调用 audio/transcriptions

返回 200 说明 Key/网络/端点都没问题——如果此时前端还识别失败，
问题就在「浏览器录出来的音频」这一段，去看 logs/backend.log 里的 ASR 警告。
"""
import io
import math
import socket
import struct
import sys
import urllib.error
import urllib.request
import uuid
import wave
from pathlib import Path

# 强制 IPv4：部分网络下域名优先解析到不可达的 IPv6，会一直挂到超时
_orig_getaddrinfo = socket.getaddrinfo
socket.getaddrinfo = lambda host, port, family=0, type=0, proto=0, flags=0: _orig_getaddrinfo(
    host, port, socket.AF_INET, type, proto, flags
)

BASE_DIR = Path(__file__).resolve().parent


def load_env():
    env = {}
    f = BASE_DIR / ".env"
    if not f.exists():
        return env
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def make_wav(seconds=3, rate=16000, freq=440):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = bytearray()
        for i in range(int(rate * seconds)):
            frames += struct.pack("<h", int(12000 * math.sin(2 * math.pi * freq * i / rate)))
        w.writeframes(bytes(frames))
    return buf.getvalue()


def transcribe(base, key, model, filename, data):
    boundary = "----check" + uuid.uuid4().hex
    body = b"".join([
        ('--%s\r\nContent-Disposition: form-data; name="model"\r\n\r\n%s\r\n' % (boundary, model)).encode(),
        ('--%s\r\nContent-Disposition: form-data; name="file"; filename="%s"\r\n'
         'Content-Type: application/octet-stream\r\n\r\n' % (boundary, filename)).encode(),
        data,
        ("\r\n--%s--\r\n" % boundary).encode(),
    ])
    req = urllib.request.Request(
        base.rstrip("/") + "/audio/transcriptions",
        data=body,
        method="POST",
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "multipart/form-data; boundary=" + boundary,
        },
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 绕开代理
    try:
        with opener.open(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as exc:
        return None, "%s: %s" % (type(exc).__name__, exc)


def main():
    env = load_env()
    base = env.get("ASR_BASE_URL", "http://api.siliconflow.cn/v1")
    key = env.get("ASR_API_KEY", "")
    model = env.get("ASR_MODEL", "FunAudioLLM/SenseVoiceSmall")

    print("=" * 56)
    print("ASR 配置")
    print("  base_url :", base)
    print("  model    :", model)
    print("  api_key  :", ("%s...%s (len=%d)" % (key[:8], key[-4:], len(key))) if key else "!! 未配置")
    print("=" * 56)
    if not key:
        print("请先在 .env 里填 ASR_API_KEY")
        return 1

    status, body = transcribe(base, key, model, "voice.wav", make_wav())
    print("请求结果 : HTTP", status)
    print("响应内容 :", body[:300])
    print()
    if status == 200:
        print("✅ Key / 网络 / 端点 全部正常。")
        print("   若前端仍识别失败，请查看 logs/backend.log 里以「ASR 识别失败」开头的行。")
        return 0
    print("❌ 调用失败。常见原因：Key 无效或额度用尽、base_url 写错、网络被代理拦截。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
