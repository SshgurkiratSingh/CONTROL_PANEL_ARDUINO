#ifndef HELPERS_H
#define HELPERS_H
#include <Arduino.h>
/**
 * Returns the amount of free RAM in bytes
 * @return Number of free bytes
 */
int getFreeRam();
#define MAX_NAME_LENGTH 15
typedef struct
{
    char name[MAX_NAME_LENGTH]; // Fixed-size string for efficiency
    int min, max, current;
} Parameter;


class ParameterStore
{
public:
    static const int MAX_PARAMS = 5;

    // Make the Parameter struct public so that the main code can use it.
    struct Parameter
    {
        char name[MAX_NAME_LENGTH];
        int min;
        int max;
        int current;
    };

private:
    Parameter params[MAX_PARAMS];
    int head;  // Next insertion index (circular buffer)
    int count; // Number of parameters stored (up to MAX_PARAMS)

public:
    ParameterStore() : head(0), count(0)
    {
        for (int i = 0; i < MAX_PARAMS; i++)
        {
            params[i].name[0] = '\0';
        }
    }

    // Add a parameter; when full, overwrites the oldest.
    void addParameter(const char *name, int min, int max, int current)
    {
        strncpy(params[head].name, name, MAX_NAME_LENGTH - 1);
        params[head].name[MAX_NAME_LENGTH - 1] = '\0'; // ensure null termination
        params[head].min = min;
        params[head].max = max;
        params[head].current = constrain(current, min, max);

        head = (head + 1) % MAX_PARAMS;
        if (count < MAX_PARAMS)
        {
            count++;
        }
    }

    // Return true if no parameters have been added.
    bool isEmpty()
    {
        return (count == 0);
    }

    // Get the number of stored parameters.
    int getCount()
    {
        return count;
    }

    // Update parameter by name; returns true if found.
    bool updateParameterValue(const char *name, int newValue)
    {
        for (int i = 0; i < MAX_PARAMS; i++)
        {
            if (strcmp(params[i].name, name) == 0)
            {
                params[i].current = constrain(newValue, params[i].min, params[i].max);
                return true;
            }
        }
        return false;
    }

    // Update parameter by index.
    void updateParameterValue(int index, int newValue)
    {
        if (index < 0 || index >= count)
            return;
        params[index].current = constrain(newValue, params[index].min, params[index].max);
    }
    // get min value of parameter
    int getParameterMinValue(const char *name)
    {
        for (int i = 0; i < MAX_PARAMS; i++)
        {
            if (strcmp(params[i].name, name) == 0)
            {
                return params[i].min;
            }
        }
        return -1;
    }
    // get max value of parameter
    int getParameterMaxValue(const char *name)
    {
        for (int i = 0; i < MAX_PARAMS; i++)
        {
            if (strcmp(params[i].name, name) == 0)
            {
                return params[i].max;
            }
        }
        return -1;
    }
    // Retrieve the current value by parameter name; returns -1 if not found.
    int getParameterCurrentValue(const char *name)
    {
        for (int i = 0; i < MAX_PARAMS; i++)
        {
            if (strcmp(params[i].name, name) == 0)
            {
                return params[i].current;
            }
        }
        return -1;
    }

    // Get a parameter by index. If index is invalid, return an empty parameter.
    Parameter getParameter(int index)
    {
        if (index < 0 || index >= count)
        {
            Parameter empty = {"", 0, 0, 0};
            return empty;
        }
        return params[index];
    }

    // Print all parameters to Serial.
    void printParametersSerial()
    {
        Serial.println("Parameters:");
        for (int i = 0; i < count; i++)
        {
            Serial.print("Index ");
            Serial.print(i);
            Serial.print(": ");
            Serial.print(params[i].name);
            Serial.print(" | Min: ");
            Serial.print(params[i].min);
            Serial.print(" | Max: ");
            Serial.print(params[i].max);
            Serial.print(" | Current: ");
            Serial.println(params[i].current);
        }
    }
};

#endif // HELPERS_H