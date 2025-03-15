#include <Arduino.h>
#include <Wire.h>
#include <ssd1306_128x64_i2c.h>
#include <RotaryEncoder.h>
#include "helpers.h"

#define BUTTON_PIN 2
#define ENCODER_CLK 3
#define ENCODER_DT 4
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1

// Initialize OLED display and rotary encoder.
ssd1306_128x64_i2c display;
RotaryEncoder encoder(ENCODER_CLK, ENCODER_DT, RotaryEncoder::LatchMode::TWO03);

// Global parameter store and selected parameter index.
ParameterStore params;
int selectedParamIndex = -1;
char buffer[32];

// --- Global variable for software name ---
// Default software name can be changed via serial command "set:software,<name>"
char softwareName[32] = "Unknown";

// --- Variables for rapid update mode ---
unsigned long lastEncoderUpdateTime = 0;
bool rapidUpdateMode = false;
const unsigned long rapidUpdateThreshold = 600;

// --- New display mode tracking to reduce clearDisplay calls ---
enum DisplayMode
{
  MODE_FULL,
  MODE_RAPID
};
DisplayMode currentDisplayMode = MODE_FULL;

// Update the full display (name, value, progress bar, and software name).
void updateOLED(const char *name, int value, int min, int max)
{
  // Only clear if we're switching from rapid to full mode.
  if (currentDisplayMode != MODE_FULL)
  {
    display.clearDisplay();
    currentDisplayMode = MODE_FULL;
  }
  sprintf(buffer, "Parameter: %s", name);
  display.drawString(0, 3, buffer);
  sprintf(buffer, "Value: %d", value);
  display.drawString(0, 4, buffer);

  // Draw the progress bar at the top.
  int pixelToMark = map(value, min, max, 0, SCREEN_WIDTH);
  for (int i = 0; i < SCREEN_WIDTH; i++)
  {
    if (i < pixelToMark)
      display.drawPixel(i, 0, BLACK);
    else
      display.drawPixel(i, 0, WHITE);
  }

  // Display the software name on the last line (line 7).
  sprintf(buffer, "Software: %s      ", softwareName);
  display.drawString(0, 7, buffer);
  // (If your library requires an explicit display update, add display.display() here)
}

// Update a rapid display showing only the parameter value and software name.
void updateOLEDRapid(const char *name, int value)
{
  // Only clear if we're switching from full to rapid mode.
  if (currentDisplayMode != MODE_RAPID)
  {
    display.clearDisplay();
    currentDisplayMode = MODE_RAPID;
  }
  sprintf(buffer, "%d   ", value); // extra spaces to overwrite previous characters
  // Center the value on the display.
  display.drawString(50, 3, buffer);
  // Display the software name on the last line (line 7).
  // (If your library requires an explicit display update, add display.display() here)
}

void processSerialCommands()
{
  if (Serial.available() > 0)
  {
    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command.startsWith("add:param"))
    {
      int firstComma = command.indexOf(',');
      if (firstComma == -1)
        return;
      String args = command.substring(firstComma + 1);
      int idx1 = args.indexOf(',');
      int idx2 = args.indexOf(',', idx1 + 1);
      int idx3 = args.indexOf(',', idx2 + 1);
      if (idx1 == -1 || idx2 == -1 || idx3 == -1)
      {
        Serial.println("ERR,Invalid add:param format");
        return;
      }
      String name = args.substring(0, idx1);
      int minVal = args.substring(idx1 + 1, idx2).toInt();
      int maxVal = args.substring(idx2 + 1, idx3).toInt();
      int curVal = args.substring(idx3 + 1).toInt();
      params.addParameter(name.c_str(), minVal, maxVal, curVal);

      if (params.getCount() == 1)
      {
        selectedParamIndex = 0;
        display.clearDisplay();
        currentDisplayMode = MODE_FULL;
        updateOLED(name.c_str(), curVal, minVal, maxVal);
      }

      Serial.print("A,");
      Serial.println(name);
    }
    else if (command.startsWith("get:paramCurval"))
    {
      int comma = command.indexOf(',');
      if (comma == -1)
      {
        Serial.println("ERR,Invalid get:paramCurval format");
        return;
      }
      String name = command.substring(comma + 1);
      int curVal = params.getParameterCurrentValue(name.c_str());
      Serial.print("G,");
      Serial.print(name);
      Serial.print(",");
      if (curVal == -1)
        Serial.println("ERROR");
      else
        Serial.println(curVal);
    }
    else if (command.startsWith("update:paramsCurval"))
    {
      int firstComma = command.indexOf(',');
      int secondComma = command.indexOf(',', firstComma + 1);
      if (firstComma == -1 || secondComma == -1)
      {
        Serial.println("ERR,Invalid update:paramsCurval format");
        return;
      }
      String name = command.substring(firstComma + 1, secondComma);
      int newValue = command.substring(secondComma + 1).toInt();
      if (params.updateParameterValue(name.c_str(), newValue))
      {
        Serial.print("U,");
        Serial.print(name);
        Serial.print(",");
        Serial.println(newValue);

        updateOLED(name.c_str(), newValue, params.getParameterMinValue(name.c_str()), params.getParameterMaxValue(name.c_str()));
      }
      else
      {
        Serial.print("U,");
        Serial.print(name);
        Serial.println(",ERROR");
      }
    }
    else if (command.startsWith("get:AlladdedParams"))
    {
      int count = params.getCount();
      for (int i = 0; i < count; i++)
      {
        ParameterStore::Parameter param = params.getParameter(i);
        Serial.print("L,");
        Serial.print(i);
        Serial.print(",");
        Serial.print(param.name);
        Serial.print(",");
        Serial.print(param.min);
        Serial.print(",");
        Serial.print(param.max);
        Serial.print(",");
        Serial.println(param.current);
      }
    }
    // New command to set the software name.
    else if (command.startsWith("set:software"))
    {
      int comma = command.indexOf(',');
      if (comma == -1)
      {
        Serial.println("ERR,Invalid set:software format");
        return;
      }
      String sname = command.substring(comma + 1);
      sname.trim();
      sname.toCharArray(softwareName, sizeof(softwareName));
      Serial.println(softwareName);

      // Update display with the new software name.
      if (selectedParamIndex >= 0)
      {
        ParameterStore::Parameter currentParam = params.getParameter(selectedParamIndex);
        if (rapidUpdateMode)
          updateOLEDRapid(currentParam.name, currentParam.current);
        else
          updateOLED(currentParam.name, currentParam.current, currentParam.min, currentParam.max);
      }
      else
      {
        display.clearDisplay();
        sprintf(buffer, "Software: %s      ", softwareName);
        display.drawString(0, 7, buffer);
      }
    }
    // New command to read a digital pin.
    else if (command.startsWith("read:digital"))
    {
      int comma = command.indexOf(',');
      if (comma == -1)
      {
        Serial.println("ERR,Invalid read:digital format");
        return;
      }
      String pinStr = command.substring(comma + 1);
      pinStr.trim();
      int pin = pinStr.toInt();
      pinMode(pin, INPUT); // Ensure the pin is set as input
      int val = digitalRead(pin);
      Serial.print("D,");
      Serial.print(pin);
      Serial.print(",");
      Serial.println(val);
    }
    // New command to read an analog pin.
    else if (command.startsWith("read:analog"))
    {
      int comma = command.indexOf(',');
      if (comma == -1)
      {
        Serial.println("ERR,Invalid read:analog format");
        return;
      }
      String pinStr = command.substring(comma + 1);
      pinStr.trim();
      int analogIndex = pinStr.toInt();
      // For many Arduino boards, analog pins are defined as A0, A1, etc.
      int analogPin = A0 + analogIndex;
      int val = analogRead(analogPin);
      Serial.print("A,");
      Serial.print(analogIndex);
      Serial.print(",");
      Serial.println(val);
    }
    else
    {
      Serial.println("ERR,Unknown command");
    }
  }
}

void setup()
{
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  Serial.begin(9600);
  display.init();
  display.clearDisplay();
  display.drawString(0, 0, "Waiting for");
  display.drawString(0, 1, "parameters...");
  currentDisplayMode = MODE_FULL;
}

void loop()
{
  processSerialCommands();

  encoder.tick();
  int delta = encoder.getPosition();
  if (delta != 0)
  {
    encoder.setPosition(0); // Reset the encoder count

    if (selectedParamIndex >= 0)
    {
      ParameterStore::Parameter currentParam = params.getParameter(selectedParamIndex);
      int newVal = constrain(currentParam.current + delta, currentParam.min, currentParam.max);

      // Update the parameter value only if it actually changes
      if (newVal != currentParam.current)
      {
        params.updateParameterValue(selectedParamIndex, newVal);
        Serial.print("U,");
        Serial.print(currentParam.name);
        Serial.print(",");
        Serial.println(newVal);

        unsigned long now = millis();
        // If updates come in rapid succession, use rapid update mode.
        if (now - lastEncoderUpdateTime < rapidUpdateThreshold)
        {
          rapidUpdateMode = true;
          updateOLEDRapid(currentParam.name, newVal);
        }
        else
        {
          rapidUpdateMode = false;
          updateOLED(currentParam.name, newVal, currentParam.min, currentParam.max);
        }
        lastEncoderUpdateTime = now;
      }
    }
  }
  else
  {
    // If in rapid update mode, check if enough time has passed to revert to normal display.
    if (rapidUpdateMode && (millis() - lastEncoderUpdateTime >= rapidUpdateThreshold))
    {
      rapidUpdateMode = false;
      if (selectedParamIndex >= 0)
      {
        ParameterStore::Parameter currentParam = params.getParameter(selectedParamIndex);
        updateOLED(currentParam.name, currentParam.current, currentParam.min, currentParam.max);
      }
    }
  }

  int reading = digitalRead(BUTTON_PIN);
  if (reading == LOW)
  {
    delay(50);
    if (digitalRead(BUTTON_PIN) == LOW)
    {
      if (!params.isEmpty())
      {
        selectedParamIndex = (selectedParamIndex + 1) % params.getCount();
        ParameterStore::Parameter p = params.getParameter(selectedParamIndex);
        Serial.print("S,");
        Serial.print(selectedParamIndex);
        Serial.print(",");
        Serial.print(p.name);
        Serial.print(",");
        Serial.println(p.current);

        // Force a full-mode update when switching parameters.
        currentDisplayMode = MODE_FULL;
        updateOLED(p.name, p.current, p.min, p.max);
      }
    }
  }

  delay(2); // Reduced delay for better responsiveness
}
