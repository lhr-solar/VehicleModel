#include <math.h>

// Analog pin connected to the voltage divider midpoint
const int ThermistorPin = A0;

// Known fixed resistor value (ohms)
const float R1 = 10000.0;

// Steinhart–Hart coefficients for the thermistor
const float c1 = 1.009249522e-03;
const float c2 = 2.378405444e-04;
const float c3 = 2.019202697e-07;

void setup() {
  // Start serial communication
  Serial.begin(9600);
}

void loop() {
  // Timestamp in milliseconds since the Arduino started
  unsigned long timestamp_ms = millis();

  // Read analog value from thermistor voltage divider (0–1023)
  int Vo = analogRead(ThermistorPin);

  // Safety check to prevent division by zero or invalid readings
  if (Vo <= 0 || Vo >= 1023) {
    Serial.print("[");
    Serial.print(timestamp_ms);
    Serial.print(" ms] ");

    Serial.print("Raw ADC: ");
    Serial.print(Vo);
    Serial.println(" | ERROR: invalid reading (check wiring / open circuit)");

    delay(500);
    return;
  }

  // Convert ADC value to voltage (0–5 V)
  float voltage = Vo * (5.0 / 1023.0);

  // Circuit assumption:
  // 5V -> Thermistor (R2) -> A0 -> Fixed resistor (R1) -> GND
  // Voltage divider math:
  // R2 = R1 * (1023 / Vo - 1)
  float R2 = R1 * (1023.0 / (float)Vo - 1.0);

  // Natural log of thermistor resistance
  float logR2 = log(R2);

  // Steinhart–Hart equation (temperature in Kelvin)
  float T = 1.0 / (c1 + logR2 * (c2 + c3 * logR2 * logR2));

  // Convert temperature units
  float Tc = T - 273.15;              // Kelvin → Celsius
  float Tf = (Tc * 9.0) / 5.0 + 32.0; // Celsius → Fahrenheit

  // Print timestamp
  Serial.print("[");
  Serial.print(timestamp_ms);
  Serial.print(" ms] ");

  // Print sensor readings
  Serial.print("ADC: ");
  Serial.print(Vo);

  Serial.print(" | Voltage: ");
  Serial.print(voltage, 3);
  Serial.print(" V");

  Serial.print(" | Temp: ");
  Serial.print(Tf, 2);
  Serial.print(" F (");
  Serial.print(Tc, 2);
  Serial.println(" C)");

  // Delay to slow output
  delay(500);
}


