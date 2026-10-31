#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""树莓派 Camera Module 3 网页拍照界面

浏览器打开 http://<树莓派IP>:8000 即可看到实时画面并点击快门拍照。
只用标准库 + picamera2，无需安装任何额外包。
"""

import io
import os
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder
from picamera2.outputs import FileOutput

PORT = 8000
SAVE_DIR = "/home/xh/captures"
BITRATE = 8000000
STILL_SIZE = (2304, 1296)
VIDEO_SIZE = (1280, 720)

os.makedirs(SAVE_DIR, exist_ok=True)


class Stream(io.BufferedIOBase):
    """把编码器输出的 JPEG 帧缓存下来，供 HTTP 线程读取。"""

    def __init__(self):
        self.frame = None
        self.cond = threading.Condition()

    def write(self, buf):
        with self.cond:
            self.frame = buf
            self.cond.notify_all()


stream = Stream()
cam = Picamera2()
video_cfg = cam.create_video_configuration(
    main={"size": VIDEO_SIZE, "format": "RGB888"}, buffer_count=4
)
still_cfg = cam.create_still_configuration(
    main={"size": STILL_SIZE}, buffer_count=1
)
cam.configure(video_cfg)
cam.start_recording(MJPEGEncoder(bitrate=BITRATE), FileOutput(stream))
CAP_LOCK = threading.Lock()


def jpeg_size(path):
    """从 JPEG 文件头解析宽高，不依赖 Pillow。"""
    try:
        with open(path, "rb") as f:
            data = f.read(300000)
    except OSError:
        return 0, 0
    i = 2
    n = len(data)
    while i + 9 < n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3):
            h = (data[i + 5] << 8) | data[i + 6]
            w = (data[i + 7] << 8) | data[i + 8]
            return w, h
        if marker == 0xD8 or marker == 0x01 or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        seglen = (data[i + 2] << 8) | data[i + 3]
        if seglen < 2:
            break
        i += 2 + seglen
    return 0, 0


def restart_stream():
    cam.start_recording(MJPEGEncoder(bitrate=BITRATE), FileOutput(stream))


def shoot():
    """拍一张全分辨率照片，返回文件名。失败时退回当前视频帧。"""
    with CAP_LOCK:
        name = "cap_%s.jpg" % datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(SAVE_DIR, name)
        cam.stop_recording()

        # 主路径：切到静态配置，全分辨率 + 自动对焦
        try:
            cam.switch_mode_and_capture_file(still_cfg, path)
        except Exception as exc:
            print("[warn] still 模式失败: %r" % (exc,), flush=True)

        # 退路：视频模式下直接取一帧
        if not os.path.isfile(path):
            try:
                cam.switch_mode(video_cfg)
                cam.start()
                req = cam.capture_request()
                req.save("main", path)
                req.release()
            except Exception as exc:
                print("[warn] 帧回退失败: %r" % (exc,), flush=True)

        # 恢复实时流
        try:
            cam.switch_mode(video_cfg)
        except Exception:
            pass
        restart_stream()
        return name


INDEX_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>云台摄像头</title>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{background:#0b0c0f;color:#e8eaed;min-height:100vh;display:flex;flex-direction:column;
       align-items:center;font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
  header{width:100%;padding:13px 18px;display:flex;justify-content:space-between;
         font-size:13px;color:#9aa0a6;border-bottom:1px solid #1e2126}
  .dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#34c759;
       margin-right:6px;animation:blink 2s infinite}
  @keyframes blink{50%{opacity:.3}}
  .stage{width:100%;max-width:820px;margin:16px auto 0;padding:0 14px}
  #live{width:100%;border-radius:14px;background:#000;display:block;aspect-ratio:16/9;object-fit:cover}
  .bar{margin:20px 0 8px;display:flex;justify-content:center}
  #shot{width:74px;height:74px;border-radius:50%;background:#fff;border:5px solid #3a3f47;
        cursor:pointer;transition:transform .08s;padding:0}
  #shot:active{transform:scale(.92)}
  #shot:disabled{background:#8b8f96;cursor:wait}
  .tip{font-size:12.5px;color:#7c8288;margin-bottom:18px;text-align:center;padding:0 20px}
  #result{width:100%;max-width:820px;padding:0 14px 40px}
  #result img{width:100%;border-radius:14px;display:block}
  .file{font-size:12.5px;margin-top:10px;text-align:center}
  .file a{color:#5fa8ff;text-decoration:none}
</style>
</head>
<body>
<header><span><span class="dot"></span>实时画面 1280×720</span><span id="clock">--:--:--</span></header>
<div class="stage"><img id="live" src="/stream" alt="实时画面"></div>
<div class="bar"><button id="shot" aria-label="拍照"></button></div>
<div class="tip" id="tip">点白色圆圈拍照</div>
<div id="result"></div>
<script>
const shot=document.getElementById('shot'),tip=document.getElementById('tip'),
      res=document.getElementById('result'),clock=document.getElementById('clock');
setInterval(()=>{clock.textContent=new Date().toLocaleTimeString('zh-CN',{hour12:false})},1000);
shot.onclick=async()=>{
  shot.disabled=true; tip.textContent='正在拍摄，请稍等…';
  try{
    const r=await fetch('/capture',{cache:'no-store'});
    const j=await r.json();
    if(j.error){ tip.textContent='拍摄失败：'+j.error; }
    else{
      tip.textContent='已保存 '+j.name+' · '+j.w+'×'+j.h+' · '+j.size+' KB';
      const img=new Image();
      img.src='/photo/'+encodeURIComponent(j.name)+'?t='+Date.now();
      res.innerHTML=''; res.appendChild(img);
      const p=document.createElement('div'); p.className='file';
      const a=document.createElement('a');
      a.href='/photo/'+encodeURIComponent(j.name); a.textContent='下载这张照片';
      a.setAttribute('download',j.name);
      p.appendChild(a); res.appendChild(p);
    }
  }catch(e){ tip.textContent='请求失败：'+e; }
  shot.disabled=false;
};
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._send_html()
        elif path == "/stream":
            self._send_stream()
        elif path == "/capture":
            self._send_capture()
        elif path.startswith("/photo/"):
            self._send_photo(path)
        else:
            self.send_error(404)

    def _send_html(self):
        body = INDEX_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=FRAME")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            while True:
                with stream.cond:
                    stream.cond.wait(timeout=10)
                    frame = stream.frame
                if frame is None:
                    continue
                self.wfile.write(b"--FRAME\r\n")
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(frame)))
                self.end_headers()
                self.wfile.write(frame)
                self.wfile.write(b"\r\n")
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _send_capture(self):
        try:
            name = shoot()
            full = os.path.join(SAVE_DIR, name)
            if not os.path.isfile(full):
                return self._json({"error": "拍照失败，未生成文件"})
            w, h = jpeg_size(full)
            payload = {
                "name": name,
                "size": int(round(os.path.getsize(full) / 1024)),
                "w": w,
                "h": h,
            }
            self._json(payload)
        except Exception as exc:
            self._json({"error": repr(exc)})

    def _send_photo(self, path):
        name = os.path.basename(unquote(path[len("/photo/"):]))
        full = os.path.join(SAVE_DIR, name)
        if not os.path.isfile(full):
            self.send_error(404)
            return
        with open(full, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj):
        import json

        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.daemon_threads = True
    print("camera web ready on port %d" % PORT, flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
