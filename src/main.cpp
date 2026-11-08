#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>
#include <Adafruit_INA219.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "config.h"

Adafruit_INA219 ina219;
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
WebServer server(80);

float voltage = 0.0;
float current = 0.0;
float power = 0.0;

void handleData() {
  StaticJsonDocument<200> doc;
  doc["voltage"] = voltage;
  doc["current"] = current;
  doc["power"] = power;
  doc["timestamp"] = millis() / 1000;
  String response;
  serializeJson(doc, response);
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", response);
}

void handleRoot() {
  String html = "<html><head><title>SolarLab Mini</title></head><body><h1>SolarLab Mini</h1><p>Go to /data for JSON</p></body></html>";
  server.send(200, "text/html", html);
}

void setup() {
  Serial.begin(115200);
  delay(100);
  
  Wire.begin(SDA_PIN, SCL_PIN);
  
  // Init OLED
  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
    Serial.println("SSD1306 allocation failed");
  } else {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 0);
    display.println("SolarLab Mini");
    display.println("Starting...");
    display.display();
  }
  
  // Init INA219
  if (!ina219.begin()) {
    Serial.println("Failed to find INA219 chip");
  } else {
    Serial.println("INA219 found");
  }
  
  // Start WiFi AP
  WiFi.mode(WIFI_AP);
  WiFi.softAP(AP_SSID, AP_PASSWORD);
  Serial.print("AP IP: ");
  Serial.println(WiFi.softAPIP());
  
  // Routes
  server.on("/", handleRoot);
  server.on("/data", handleData);
  server.begin();
  Serial.println("HTTP server started");
}

void loop() {
  server.handleClient();
  
  // Read sensors
  voltage = ina219.getBusVoltage_V();
  current = ina219.getCurrent_mA() / 1000.0;
  power = voltage * current;
  
  // Update OLED
  display.clearDisplay();
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println("SolarLab Mini");
  display.setCursor(0, 16);
  display.print("V:"); display.print(voltage, 2); display.println("V");
  display.setCursor(0, 28);
  display.print("I:"); display.print(current, 3); display.println("A");
  display.setCursor(0, 40);
  display.print("P:"); display.print(power, 2); display.println("W");
  display.setCursor(0, 52);
  display.print("AP: "); display.print(AP_SSID);
  display.display();
  
  delay(1000);
}
