//replay transmitter for the dashboard control tab

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "rom/ets_sys.h"

#define PIN_SCK  7
#define PIN_MISO 8
#define PIN_MOSI 9
#define PIN_CSN  44
#define PIN_GDO0 43

#define READ_BURST  0xC0
#define SRES  0x30
#define STX   0x35
#define VERSION 0x31
#define MAXP  1024

static inline void sck(int v)  { gpio_set_level(PIN_SCK, v); }
static inline void mosi(int v) { gpio_set_level(PIN_MOSI, v); }
static inline void csn(int v)  { gpio_set_level(PIN_CSN, v); }
static inline int  miso(void)  { return gpio_get_level(PIN_MISO); }

static uint8_t xfer(uint8_t out)
{
    uint8_t in = 0;
    for (int i = 0; i < 8; i++) {
        mosi((out & 0x80) ? 1 : 0);
        out <<= 1;
        ets_delay_us(1); sck(1);
        in = (in << 1) | miso();
        ets_delay_us(1); sck(0);
    }
    return in;
}

static void select(void) { csn(0); for (int i=0;i<10000 && miso();i++) ets_delay_us(1); }
static void wr_reg(uint8_t a, uint8_t v) { select(); xfer(a); xfer(v); csn(1); }
static void strobe(uint8_t s)            { select(); xfer(s); csn(1); }
static uint8_t rd_status(uint8_t a) { select(); xfer(a|READ_BURST); uint8_t v=xfer(0); csn(1); return v; }

//async ook tx at 433.92
static const uint8_t cfg[][2] = {
    {0x02,0x2E},{0x03,0x47},{0x08,0x30},{0x0B,0x06},{0x0D,0x10},{0x0E,0xB0},
    {0x0F,0x71},{0x10,0x87},{0x11,0x00},{0x12,0x30},{0x13,0x32},{0x14,0xF8},
    {0x18,0x18},{0x22,0x11},{0x23,0xE9},{0x24,0x2A},{0x25,0x00},{0x26,0x1F},
    {0x2C,0x81},{0x2D,0x35},{0x2E,0x09},
};

static void set_patable(void) { select(); xfer(0x3E|0x40); xfer(0x00); xfer(0x60); csn(1); }

static int durs[MAXP];

static int parse_line(char *line)
{
    int n = 0;
    char *p = line;
    if (*p == 'P') p++;
    while (*p && n < MAXP) {
        durs[n++] = atoi(p);
        while (*p && *p != ',') p++;
        if (*p == ',') p++;
    }
    return n;
}

static void replay(int n)
{
    for (int r = 0; r < 5; r++) {
        for (int i = 0; i < n; i++) {
            gpio_set_level(PIN_GDO0, (i & 1) ? 0 : 1);
            ets_delay_us(durs[i] > 0 ? durs[i] : 1);
        }
        gpio_set_level(PIN_GDO0, 0);
        vTaskDelay(pdMS_TO_TICKS(20));      //also feeds the wdt
    }
}

void app_main(void)
{
    setvbuf(stdout, NULL, _IONBF, 0);

    gpio_config_t out = { .pin_bit_mask=(1ULL<<PIN_SCK)|(1ULL<<PIN_MOSI)|(1ULL<<PIN_CSN)|(1ULL<<PIN_GDO0),
                          .mode=GPIO_MODE_OUTPUT };
    gpio_config(&out);
    gpio_config_t in = { .pin_bit_mask=(1ULL<<PIN_MISO), .mode=GPIO_MODE_INPUT };
    gpio_config(&in);

    csn(1); sck(0); mosi(0); gpio_set_level(PIN_GDO0, 0);
    ets_delay_us(100);
    csn(0); ets_delay_us(10); csn(1); ets_delay_us(50);
    strobe(SRES); ets_delay_us(200);

    uint8_t ver = rd_status(VERSION);
    printf("cc1101 replay, version 0x%02X\n", ver);
    if (ver == 0x00 || ver == 0xFF) { printf("no cc1101\n"); return; }
    for (int i = 0; i < (int)(sizeof(cfg)/2); i++) wr_reg(cfg[i][0], cfg[i][1]);
    set_patable();
    strobe(STX);
    printf("replay ready, send P<us>,<us>,...\n");

    char line[8192];
    int k = 0;
    while (1) {
        int c = getchar();
        if (c == EOF) { vTaskDelay(pdMS_TO_TICKS(5)); continue; }
        if (c == '\n' || k == sizeof(line) - 1) {
            line[k] = 0;
            if (k > 1) { int n = parse_line(line); replay(n); printf("replayed %d pulses x5\n", n); }
            k = 0;
        } else if (c != '\r') {
            line[k++] = c;
        }
    }
}
