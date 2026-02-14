// Analog pin connected to the voltage divider midpoint
const int ThermistorPin = A0;

// Raw analog value read from the pin (0–1023)
int Vo;

// Known fixed resistor value 
const float R1 = 10000.0;

// Variables for thermistor math
float logR2, R2;     // thermistor resistance and its natural log
float T, Tc, Tf;    // temperature in Kelvin, Celsius, Fahrenheit

// Steinhart–Hart coefficients for the thermistor
const float c1 = 1.009249522e-03;
const float c2 = 2.378405444e-04;
const float c3 = 2.019202697e-07;

void setup() {
  // Start serial communication so we can see values in Serial Monitor
  Serial.begin(9600);
}

void loop() {

  // Read the analog voltage from the thermistor voltage divider
  Vo = analogRead(ThermistorPin);

  // Convert ADC value to actual voltage (0–5V range)
  float voltage = Vo * (5.0 / 1023.0);

  // Calculate thermistor resistance using the voltage divider equation
  // Assumes: 5V -> R1 -> A0 -> thermistor -> GND
  R2 = R1 * (1023.0 / (float)Vo - 1.0);

  // Take natural logarithm of the thermistor resistance
  logR2 = log(R2);

  // Apply Steinhart–Hart equation to get temperature in Kelvin
  T = 1.0 / (c1 + logR2 * (c2 + c3 * logR2 * logR2));

  // Convert Kelvin to Celsius
  Tc = T - 273.15;

  // Convert Celsius to Fahrenheit
  Tf = (Tc * 9.0) / 5.0 + 32.0;

  // Print raw ADC reading
  Serial.print("Raw ADC: ");
  Serial.print(Vo);

  // Print measured voltage
  Serial.print(" | Voltage: ");
  Serial.print(voltage, 3);
  Serial.print(" V");

  // Print temperature in Fahrenheit and Celsius
  Serial.print(" | Temperature: ");
  Serial.print(Tf);
  Serial.print(" F; ");
  Serial.print(Tc);
  Serial.println(" C");

  // Small delay to slow down serial output
  delay(500);
}
