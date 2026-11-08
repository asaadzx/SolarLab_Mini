#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "config.h"

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_ADDR 0x3C

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

void setup() {
  Serial.begin(115200);
  delay(100);
  
  Wire.begin(21, 22);
  
  if (display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 0);
    display.println("WiFi Test");
    display.display();
  }
  
  Serial.print("Connecting to ");
  Serial.println(WIFI_SSID);
  
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  Serial.println();
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("WiFi connected!");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
    Serial.print("RSSI: ");
    Serial.println(WiFi.RSSI());
    Serial.print("MAC: ");
    Serial.println(WiFi.macAddress());
    
    display.clearDisplay();
    display.setCursor(0, 0);
    display.println("Connected");
    display.print("IP:");
    display.println(WiFi.localIP());
    display.print("RSSI:");
    display.println(WiFi.RSSI());
    display.display();
    
    // Try to fetch Wikipedia
    HTTPClient http;
    http.begin("https://en.wikipedia.org/wiki/Solar_cell");
    int httpCode = http.GET();
    Serial.print("HTTP Code: ");
    Serial.println(httpCode);
    if (httpCode > 0) {
      String payload = http.getString();
      Serial.println("Got response, length: " + String(payload.length()));
      // Show first 60 chars
      display.clearDisplay();
      display.setCursor(0, 0);
      display.println("Fetched Wiki");
      display.println("Len: " + String(payload.length()));
      display.display();
    }
    http.end();
  } else {
    Serial.println("WiFi failed!");
    display.clearDisplay();
    display.setCursor(0, 0);
    display.println("WiFi Failed");
    display.display();
  }
}

void loop() {
  delay(5000);
}
