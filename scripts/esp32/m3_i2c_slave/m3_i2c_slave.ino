// M3：ESP32 作 I2C 从机，收 Pi 发来的 dx dy 并打串口
//
// 协议（与 M0 验证过的完全一致，没改）
//   地址 0x08
//   4 字节：dx(int16 小端) + dy(int16 小端)
//   主机读 1 字节时回 0x42，用来确认"从机活着"
//
// 注意：不能用 Serial.print 在 receiveEvent 里打印。
// 中断里做串口输出会卡死总线，所以中断只存数据，由 loop 打印。

#include <Wire.h>

#define I2C_SLAVE_ADDR 0x08

volatile int16_t  g_dx    = 0;
volatile int16_t  g_dy    = 0;
volatile bool     g_new   = false;
volatile uint32_t g_count = 0;

void receiveEvent(int howMany) {
  if (howMany >= 4) {
    uint8_t buf[4];
    for (int i = 0; i < 4; i++) buf[i] = Wire.read();
    // 小端拼接：低字节在前
    g_dx = (int16_t)(buf[0] | (buf[1] << 8));
    g_dy = (int16_t)(buf[2] | (buf[3] << 8));
    g_count++;
    g_new = true;
  }
  while (Wire.available()) Wire.read();   // 丢弃多余字节，防止下帧错位
}

void requestEvent() {
  Wire.write(0x42);
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Wire.begin(I2C_SLAVE_ADDR);
  Wire.onReceive(receiveEvent);
  Wire.onRequest(requestEvent);

  Serial.println();
  Serial.println("=== I2C SLAVE READY  addr=0x08 ===");
  Serial.println("waiting: 4 bytes = dx(int16 LE) + dy(int16 LE)");
}

void loop() {
  if (g_new) {
    g_new = false;
    int16_t dx = g_dx;
    int16_t dy = g_dy;
    Serial.printf("#%lu  recv dx=%d  dy=%d\n",
                  (unsigned long)g_count, dx, dy);
  }
}
