#!/usr/bin/env python3
# M1：从 Camera Module 3 取 numpy 帧，测帧率，存一张灰度图
# 运行位置：树莓派 5 本机（不是 Windows，也不是虚拟机）
# 用法：python3 m1_capture.py

import time
import cv2
from picamera2 import Picamera2

W, H = 1280, 720
N = 200
OUT = "/home/xh/m1_gray.png"

picam = Picamera2()
cfg = picam.create_preview_configuration(main={"size": (W, H), "format": "RGB888"})
picam.configure(cfg)
picam.start()
time.sleep(1.0)

frame = picam.capture_array()
print("shape =", frame.shape, "dtype =", frame.dtype)

t0 = time.perf_counter()
for _ in range(N):
    frame = picam.capture_array()
t1 = time.perf_counter()

dt = t1 - t0
print("frames  = %d" % N)
print("elapsed = %.3f s" % dt)
print("avg fps = %.2f" % (N / dt))

gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
cv2.imwrite(OUT, gray)
print("saved   = %s  gray.shape = %s" % (OUT, gray.shape))

picam.stop()
