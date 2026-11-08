#!/usr/bin/env python3
# M3：算一次 dx dy，通过 I2C 发给 ESP32（从机 0x08），连发 3 次验证
#
# 前置：ESP32 已烧 m3_i2c_slave.ino，串口监视器开着
# 跑法：python3 /home/xh/m3_send.py

import struct
import subprocess
import time

import numpy as np
import cv2
from picamera2 import Picamera2

W, H = 1280, 720
I2C_BUS = "1"
I2C_ADDR = "0x08"
I2C_TOOL = "/usr/sbin/i2ctransfer"    # 必须用 i2ctransfer，不能用 i2cget

# ================= 阈值区（沿用 M2 跑通的值）=================
LOW1,  HIGH1 = (  0, 120, 80), ( 10, 255, 255)
LOW2,  HIGH2 = (165, 120, 80), (179, 255, 255)
MIN_AREA = 2000
# ===========================================================

# ===== 你要决定的东西就在下面这一行 =====
# dx>0 表示目标在画面右侧。发出去之前要不要翻符号，取决于"方向由谁定"。
SIGN_X = 1
SIGN_Y = 1
# ========================================


def detect(frame):
    """返回 (dx, dy, area) 或 None"""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    m1 = cv2.inRange(hsv, np.array(LOW1, np.uint8), np.array(HIGH1, np.uint8))
    m2 = cv2.inRange(hsv, np.array(LOW2, np.uint8), np.array(HIGH2, np.uint8))
    mask = cv2.bitwise_or(m1, m2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    for c in contours:
        area = cv2.contourArea(c)
        if area < MIN_AREA:
            continue
        if best is None or area > best[0]:
            x, y, w, h = cv2.boundingRect(c)
            best = (area, x + w // 2, y + h // 2)

    if best is None:
        return None
    area, cx, cy = best
    return cx - W // 2, cy - H // 2, int(area)


def send(dx, dy):
    """把 dx dy 打包成 4 字节，用 i2ctransfer 写过去"""
    payload = struct.pack("<hh", dx, dy)          # <hh = 两个小端 int16
    args = [I2C_TOOL, "-y", I2C_BUS, "w%d@%s" % (len(payload), I2C_ADDR)]
    args += ["0x%02x" % b for b in payload]
    r = subprocess.run(args, capture_output=True, text=True, timeout=2)
    return r.returncode, " ".join(args)


def main():
    picam = Picamera2()
    picam.configure(picam.create_preview_configuration(
        main={"size": (W, H), "format": "RGB888"}))
    picam.start()
    time.sleep(1.5)
    frame = picam.capture_array()
    picam.stop()

    result = detect(frame)
    if result is None:
        print("画面里没找到目标，不发送")
        return

    dx, dy, area = result
    dx_out = dx * SIGN_X
    dy_out = dy * SIGN_Y

    print("检测: area=%d  dx=%d dy=%d" % (area, dx, dy))
    print("发送: dx=%d dy=%d  (SIGN_X=%d SIGN_Y=%d)"
          % (dx_out, dy_out, SIGN_X, SIGN_Y))

    for i in range(3):
        rc, cmd = send(dx_out, dy_out)
        print("  第 %d 次 rc=%d   %s" % (i + 1, rc, cmd))
        if rc != 0:
            print("  发送失败，检查接线和 /dev/i2c-1 是否存在")
            return
        time.sleep(0.3)

    print("完成：看 ESP32 串口是否出现 3 行 recv")


if __name__ == "__main__":
    main()
