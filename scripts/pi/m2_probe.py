#!/usr/bin/env python3
# M2 第 1 步：探测目标的 HSV 数值（这一步不检测、不画框，只测数字）
#
# 用法：
#   1. 把红色目标物（红球/红杯子/红袜子团）放在画面正中间，让它基本占满中心那一小块
#   2. 运行 python3 m2_probe.py
#   3. 看终端打印的 H / S / V 范围，这就是你填阈值的依据
#
# 为什么要有这一步：阈值不能拍脑袋猜，得先从真实画面里量出来。

import time
import numpy as np
import cv2
from picamera2 import Picamera2

W, H = 1280, 720
HALF = 60          # 取中心 120x120 的区域
OUT = "/home/xh/m2_probe.png"

picam = Picamera2()
picam.configure(picam.create_preview_configuration(
    main={"size": (W, H), "format": "RGB888"}))
picam.start()
time.sleep(1.5)

frame = picam.capture_array()

# picamera2 在 Pi5/PISP 上虽然 format 写的是 RGB888，
# 但 capture_array() 实际给出来的数组是 BGR 序（2026-10-31 实测确认）。
# 所以这里必须用 BGR2HSV。用 RGB2HSV 会让红色读成蓝色。
hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

cx, cy = W // 2, H // 2
patch = hsv[cy - HALF:cy + HALF, cx - HALF:cx + HALF]

h = patch[:, :, 0].astype(int)
s = patch[:, :, 1].astype(int)
v = patch[:, :, 2].astype(int)


def report(name, arr):
    lo5, hi95 = np.percentile(arr, [5, 95])
    print("%s  范围 %3d ~ %3d   中位数 %3d   5%%~95%% : %3d ~ %3d"
          % (name, arr.min(), arr.max(), int(np.median(arr)), int(lo5), int(hi95)))


print("=== 画面中心 120x120 区域 ===")
report("H ", h)
report("S ", s)
report("V ", v)

hist = np.bincount(hsv[:, :, 0].ravel(), minlength=180)
top = np.argsort(hist)[::-1][:8]
print("整个画面里出现最多的 8 个 H 值:", " ".join(str(int(t)) for t in top))

# frame 本身已经是 BGR 序，cv2.imwrite 要的就是 BGR，直接存，不要再转换
cv2.imwrite(OUT, frame)
print("存图:", OUT)

picam.stop()
