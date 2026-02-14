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
  Serial.begin(9600);
}

void loop() {
  // Read ADC value (0–1023)
  int Vo = analogRead(ThermistorPin);

  // Safety check: avoid division-by-zero and extreme readings
  // Vo == 0 can happen if the circuit is open, Vo == 1023 can happen if it's shorted to 5V
  if (Vo <= 0 || Vo >= 1023) {
    Serial.print("Raw ADC: ");
    Serial.print(Vo);
    Serial.println(" | ERROR: invalid reading (check wiring / open circuit)");
    delay(500);
    return;
  }

  // Convert ADC reading to voltage (0–5V range)
  float voltage = Vo * (5.0 / 1023.0);

  // Circuit assumption for THIS formula:
  // 5V -> Thermistor (R2) -> A0 -> Fixed resistor (R1) -> GND
  // Then: R2 = R1 * (1023/Vo - 1)
  float R2 = R1 * (1023.0 / (float)Vo - 1.0);

  float logR2 = log(R2);

  // Steinhart–Hart equation (Kelvin)
  float T = 1.0 / (c1 + logR2 * (c2 + c3 * logR2 * logR2));

  // Convert to Celsius / Fahrenheit
  float Tc = T - 273.15;
  float Tf = (Tc * 9.0) / 5.0 + 32.0;

  // Print values
  Serial.print("Raw ADC: ");
  Serial.print(Vo);

  Serial.print(" | Voltage: ");
  Serial.print(voltage, 3);
  Serial.print(" V");

  Serial.print(" | Temperature: ");
  Serial.print(Tf, 2);
  Serial.print(" F; ");
  Serial.print(Tc, 2);
  Serial.println(" C");

  delay(500);
}
