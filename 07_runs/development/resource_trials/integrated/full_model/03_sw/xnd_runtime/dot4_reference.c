#include <stdint.h>

/* Software oracle used to compare against the RTL dot4 unit. */
int32_t dot4_reference(uint32_t a_word, uint32_t b_word) {
    int32_t sum = 0;
    for (unsigned lane = 0; lane < 4; ++lane) {
        int8_t a = (int8_t)((a_word >> (8u * lane)) & 0xffu);
        int8_t b = (int8_t)((b_word >> (8u * lane)) & 0xffu);
        sum += (int32_t)a * (int32_t)b;
    }
    return sum;
}
