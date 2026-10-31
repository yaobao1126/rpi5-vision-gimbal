// D13 方波自检 —— 不接舵机，只验证 ESP32 的 D13 引脚到底有没有输出
// 用法：拔掉舵机橙色信号线，烧这个程序，万用表直流电压档量 D13 对 GND
// 预期：串口每 0.5 秒打印 HIGH / LOW，电压在 3.3V 和 0V 之间跳

#define TEST_PIN 13

void setup() {
  Serial.begin(115200);
  delay(300);
  pinMode(TEST_PIN, OUTPUT);
  Serial.println("=== PIN13 TEST READY ===");
}

void loop() {
  digitalWrite(TEST_PIN, HIGH);
  Serial.println("HIGH 3.3V");
  delay(500);

  digitalWrite(TEST_PIN, LOW);
  Serial.println("LOW  0V");
  delay(500);
}
