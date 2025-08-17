#include "Log.h"
#if defined(ESP32) || defined(ARDUINO_ARCH_ESP32) || defined(_ARDUINO_ESP32_)
    #include <ESP.h>
#endif

void printFreeRam()
{
#ifdef BOTTANGO_DEBUG
    #if defined(ESP32) || defined(ARDUINO_ARCH_ESP32) || defined(_ARDUINO_ESP32_)
        uint32_t freeRam = ESP.getFreeHeap();
    #else
        extern int __heap_start, *__brkval;
        int v;
        int freeRam = (int)&v - (__brkval == 0 ? (int)&__heap_start : (int)__brkval);
    #endif

    LOG_MKBUF;
    LOG(F("Free Ram: "));
    LOG_INT(freeRam);
    LOG_NEWLINE();
#endif
}