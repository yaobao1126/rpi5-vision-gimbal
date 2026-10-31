#!/usr/bin/env python3
# M2 第 2 步：HSV 阈值找红色目标，画外接矩形 + 中心点
#
# 用法：改下面的阈值区 -> 跑 -> 看图 -> 再改，循环到框正好套住苹果为止。
# 阈值区里的数是我瞎猜的初值，不是答案，你必须自己试出来。

import time
import numpy as np
import cv2
from picamera2 import Picamera2

W, H = 1280, 720
OUT = "/home/xh/m2_detect.png"

# ================= 阈值区：只改这里 =================
# 每个阈值是 (H, S, V)。H 的合法范围 0~179，S 和 V 是 0~255。
# 红色横跨色环两端，所以拆成两段，最后取并集。
LOW1,  HIGH1 = (  0, 120,  80), ( 10, 255, 255)   # 0 这一端
LOW2,  HIGH2 = (165, 120,  80), (179, 255, 255)   # 179 那一端
MIN_AREA = 2000          # 只当"噪声闸门"用，不负责挑目标：小于这个面积的直接扔
                         # 别用它去筛掉干扰物，目标拉远后面积会大幅缩水（实测 95k→34k）
# ====================================================

picam = Picamera2()
picam.configure(picam.create_preview_configuration(
    main={"size": (W, H), "format": "RGB888"}))
picam.start()
time.sleep(1.5)
frame = picam.capture_array()

# capture_array 给的是 BGR 序，所以是 BGR2HSV
hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

mask1 = cv2.inRange(hsv, np.array(LOW1, np.uint8), np.array(HIGH1, np.uint8))
mask2 = cv2.inRange(hsv, np.array(LOW2, np.uint8), np.array(HIGH2, np.uint8))
mask = cv2.bitwise_or(mask1, mask2)

# 开运算：把零散的小白点擦掉，避免一堆噪点各算一个色块
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))

contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

out = frame.copy()

# 第一步：只挑一个，不画。候选里面积最大的那个才当目标。
best = None          # (area, x, y, w, h)
kept = 0
for c in contours:
    area = cv2.contourArea(c)
    if area < MIN_AREA:
        continue
    kept += 1
    if best is None or area > best[0]:
        x, y, w, h = cv2.boundingRect(c)
        best = (area, x, y, w, h)

# 第二步：挑完了再画，画面上永远只有一个框
if best is not None:
    area, x, y, w, h = best
    cv2.rectangle(out, (x, y), (x + w, y + h), (0, 255, 0), 2)
    cx, cy = x + w // 2, y + h // 2
    cv2.drawMarker(out, (cx, cy), (0, 255, 0), cv2.MARKER_CROSS, 24, 2)

# 画面正中心画一个黄十字，方便肉眼看偏差
cv2.drawMarker(out, (W // 2, H // 2), (0, 255, 255), cv2.MARKER_CROSS, 40, 2)

print("候选色块数: %d（>%d 像素的才算候选）" % (kept, MIN_AREA))
if best:
    area, x, y, w, h = best
    print("目标 area=%d  框=(%d,%d) %dx%d  中心=(%d,%d)  画面中心=(%d,%d)  dx=%d dy=%d"
          % (area, x, y, w, h, cx, cy, W // 2, H // 2,
             cx - W // 2, cy - H // 2))
    if kept > 1:
        print("另外 %d 个候选比它小，已忽略" % (kept - 1))
else:
    print("一个色块都没找到 —— 阈值太紧，或者目标不在画面里")

cv2.imwrite(OUT, out)
print("存图:", OUT)
picam.stop()
