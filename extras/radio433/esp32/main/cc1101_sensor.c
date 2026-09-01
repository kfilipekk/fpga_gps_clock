//beacons the chip temperature and mic sound level every second as a nexus frame

#include <stdio.h>
#include <math.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "driver/temperature_sensor.h"
#include "driver/i2s_pdm.h"
#include "rom/ets_sys.h"

#define PIN_SCK  7
#define PIN_MISO 8
#define PIN_MOSI 9
#define PIN_CSN  44
#define PIN_GDO0 43
#define PIN_MIC_CLK 42
#define PIN_MIC_DAT 41

#define READ_BURST 0xC0
#define SRES 0x30
#define STX  0x35
#define VERSION 0x31

#define PULSE 500
#define ZERO  1000
#define ONE   2000
#define RESET 4000               //under rtl_433's reset limit so repeats group
#define FRAMES 8                 //rtl_433 wants 3+ identical rows
#define DEV_ID 0xA3

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

//id, flags, temp x10 (12 bit), 0xf, humidity
static void nexus_bits(int temp_c10, int humi, uint8_t bits[36])
{
    int t12 = temp_c10 & 0xFFF;
    int flags = (1 << 3);                    //battery ok, ch1
    uint8_t b[4] = { DEV_ID, (flags << 4) | (t12 >> 8), t12 & 0xFF,
                     0xF0 | ((humi >> 4) & 0xF) };
    int k = 0;
    for (int i = 0; i < 4; i++)
        for (int j = 7; j >= 0; j--) bits[k++] = (b[i] >> j) & 1;
    for (int j = 3; j >= 0; j--) bits[k++] = (humi >> j) & 1;
}

static void send_frame(const uint8_t bits[36])
{
    for (int i = 0; i < 36; i++) {
        gpio_set_level(PIN_GDO0, 1); ets_delay_us(PULSE);
        gpio_set_level(PIN_GDO0, 0); ets_delay_us(bits[i] ? ONE : ZERO);
    }
    gpio_set_level(PIN_GDO0, 1); ets_delay_us(PULSE);
    gpio_set_level(PIN_GDO0, 0); ets_delay_us(RESET);
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

    //retry, a marginal spi contact used to stop the beacon dead
    uint8_t ver = 0xFF;
    for (int t = 0; t < 20 && (ver == 0x00 || ver == 0xFF); t++) {
        strobe(SRES); ets_delay_us(200);
        ver = rd_status(VERSION);
        if (ver == 0x00 || ver == 0xFF) vTaskDelay(pdMS_TO_TICKS(100));
    }
    printf("cc1101 sensor, version 0x%02X\n", ver);
    if (ver == 0x00 || ver == 0xFF) { printf("no cc1101 after retries\n"); return; }
    for (int i = 0; i < (int)(sizeof(cfg)/2); i++) wr_reg(cfg[i][0], cfg[i][1]);
    set_patable();
    strobe(STX);

    i2s_chan_handle_t mic = NULL;
    i2s_chan_config_t chcfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
    i2s_new_channel(&chcfg, NULL, &mic);
    i2s_pdm_rx_config_t pcfg = {
        .clk_cfg  = I2S_PDM_RX_CLK_DEFAULT_CONFIG(16000),
        .slot_cfg = I2S_PDM_RX_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO),
        .gpio_cfg = { .clk = PIN_MIC_CLK, .din = PIN_MIC_DAT },
    };
    i2s_channel_init_pdm_rx_mode(mic, &pcfg);
    i2s_channel_enable(mic);

    temperature_sensor_handle_t ts;
    temperature_sensor_config_t tcfg = TEMPERATURE_SENSOR_CONFIG_DEFAULT(-10, 80);
    temperature_sensor_install(&tcfg, &ts);
    temperature_sensor_enable(ts);

    printf("beaconing nexus id 0x%02X every 1 s (temp + mic sound level)\n", DEV_ID);
    static int16_t sbuf[512];
    uint8_t bits[36];
    while (1) {
        float tc = 0;
        temperature_sensor_get_celsius(ts, &tc);

        size_t br = 0;                               //rms level scaled to 1-100
        int humi = 1;
        if (i2s_channel_read(mic, sbuf, sizeof(sbuf), &br, 200) == ESP_OK && br) {
            int nn = br / 2;
            double sum = 0;
            for (int i = 0; i < nn; i++) sum += (double)sbuf[i] * sbuf[i];
            int lvl = (int)(20.0 * log10(sqrt(sum / nn) + 1.0)) - 20;
            humi = lvl < 1 ? 1 : lvl > 100 ? 100 : lvl;
        }

        nexus_bits((int)(tc * 10), humi, bits);
        for (int f = 0; f < FRAMES; f++) send_frame(bits);
        printf("sent %.1f C  sound %d\n", tc, humi);
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
