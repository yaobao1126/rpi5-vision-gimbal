// MG90S 舵机动作测试（不依赖 ESP32Servo 库，直接 LEDC 输出 50Hz PWM）
// 上电流程：定在 90 度 -> 小幅摆 60/120 五次 -> 全行程扫动
//
// 接线（最小系统，不经过面包板）：
//   橙/黄 = 信号 -> ESP32 的 D13 排针（一根线直达，中间不接任何东西）
//   红    = 正极 -> 5V 电源正极（浸锡硬针直接插进舵机线的红色槽）
//   棕/黑 = 地   -> 公对公线 -> 面包板最下边那条 − 轨
//
//   5V 电源负极 -> 同一条 − 轨（相邻 3 个孔以内）
//   ESP32 GND  -> 同一条 − 轨（相邻 3 个孔以内）
//   三个点在同一个孔段上才叫共地，少一个舵机就不会动

#define SERVO_PIN 13
#define FREQ_HZ   50
#define RES_BITS  14
#define CNT_MAX   (1 << RES_BITS)

void setAngle(int deg) {
  if (deg < 0)   deg = 0;
  if (deg > 180) deg = 180;
  float ms = 0.5f + (deg / 180.0f) * 2.0f;
  uint32_t duty = (uint32_t)((ms / 20.0f) * CNT_MAX);
  ledcWrite(SERVO_PIN, duty);
}

void setup() {
  Serial.begin(115200);
  delay(300);
  ledcAttach(SERVO_PIN, FREQ_HZ, RES_BITS);
  Serial.println("=== SERVO SWEEP READY  pin=D13 ===");
  setAngle(90);
  Serial.println("hold 90");
  delay(1500);
}

void loop() {
  Serial.println("--- wiggle 60 / 120 x5 ---");
  for (int i = 0; i < 5; i++) {
    setAngle(60);
    delay(600);
    setAngle(120);
    delay(600);
  }

  Serial.println("--- full sweep 0-180 ---");
  for (int a = 0; a <= 180; a += 5) {
    setAngle(a);
    delay(40);
  }
  for (int a = 180; a >= 0; a -= 5) {
    setAngle(a);
    delay(40);
  }
}
