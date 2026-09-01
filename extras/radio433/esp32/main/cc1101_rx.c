//receives the fpga's transcoded nexus frame

#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "driver/gpio.h"
#include "driver/rmt_rx.h"
#include "esp_timer.h"
#include "rom/ets_sys.h"

#define PIN_SCK  7
#define PIN_MISO 8
#define PIN_MOSI 9
#define PIN_CSN  44
#define PIN_GDO0 43

#define READ_BURST 0xC0
#define SRES 0x30
#define SRX  0x34
#define VERSION 0x31

#define OUR_ID   0xA3

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

//the rx set from spi_cfg.v
static const uint8_t cfg[][2] = {
    {0x02,0x0D},{0x03,0x47},{0x08,0x30},{0x0B,0x06},{0x0D,0x10},{0x0E,0xB0},
    {0x0F,0x71},{0x10,0x87},{0x11,0x00},{0x12,0x30},{0x13,0x32},{0x14,0xF8},
    {0x18,0x18},{0x19,0x16},{0x1B,0x43},{0x1C,0x40},{0x1D,0x93},{0x20,0xFB},
    {0x21,0x56},{0x22,0x11},{0x23,0xE9},{0x24,0x2A},{0x25,0x00},{0x26,0x1F},
    {0x2C,0x81},{0x2D,0x35},{0x2E,0x09},
};

//9 nibbles: id id flags temp temp temp f humi humi
static void try_decode(const int *bits, int n)
{
    static uint32_t last_print = 0;
    if (n < 36) return;
    uint8_t b[5] = {0, 0, 0, 0, 0};
    for (int k = 0; k < 36; k++) b[k / 8] |= bits[k] << (7 - k % 8);
    if ((b[3] & 0xF0) != 0xF0) return;
    if (esp_timer_get_time() - last_print < 500000) return;   //one per burst
    int t = ((b[1] & 0xF) << 8) | b[2];
    if (t & 0x800) t -= 0x1000;
    int humi = ((b[3] & 0xF) << 4) | (b[4] >> 4);
    if (b[0] == OUR_ID)
        printf("rx: ESP32-S3 id 0x%02X %.1fC sound %d\n", b[0], t / 10.0, humi);
    else
        printf("rx: Nexus-TH id 0x%02X %.1fC %d%% rh\n", b[0], t / 10.0, humi);
    last_print = esp_timer_get_time();
}

//the agc fills the gaps with noise, so there is no idle to frame
#define WIN 64
static void decode_symbols(const rmt_symbol_word_t *s, int n)
{
    static int bits[WIN], nbits = 0, armed = 0;
    for (int i = 0; i < n; i++) {
        const uint16_t dur[2] = {s[i].duration0, s[i].duration1};
        for (int h = 0; h < 2; h++) {
            uint32_t w = dur[h];
            if (w == 0) continue;
            if (armed) {
                armed = 0;
                if (w > 700 && w < 2500) {
                    if (nbits == WIN) {
                        for (int k = 1; k < WIN; k++) bits[k-1] = bits[k];
                        nbits = WIN - 1;
                    }
                    bits[nbits++] = (w > 1500) ? 1 : 0;
                    if (nbits >= 36) try_decode(bits + nbits - 36, 36);
                } else nbits = 0;
            } else if (w > 300 && w < 800) {
                armed = 1;
            } else nbits = 0;
        }
    }
}

static QueueHandle_t rx_q;

static bool on_recv(rmt_channel_handle_t ch, const rmt_rx_done_event_data_t *ed, void *ctx)
{
    BaseType_t hp = pdFALSE;
    xQueueSendFromISR(rx_q, ed, &hp);
    return hp == pdTRUE;
}

void app_main(void)
{
    setvbuf(stdout, NULL, _IONBF, 0);

    gpio_config_t out = { .pin_bit_mask=(1ULL<<PIN_SCK)|(1ULL<<PIN_MOSI)|(1ULL<<PIN_CSN),
                          .mode=GPIO_MODE_OUTPUT };
    gpio_config(&out);
    gpio_config_t in = { .pin_bit_mask=(1ULL<<PIN_MISO), .mode=GPIO_MODE_INPUT };
    gpio_config(&in);

    csn(1); sck(0); mosi(0);
    ets_delay_us(100);
    csn(0); ets_delay_us(10); csn(1); ets_delay_us(50);
    strobe(SRES); ets_delay_us(200);

    uint8_t ver = rd_status(VERSION);
    printf("cc1101 rx, version 0x%02X\n", ver);
    if (ver == 0x00 || ver == 0xFF) { printf("no cc1101\n"); return; }
    for (int i = 0; i < (int)(sizeof(cfg)/2); i++) wr_reg(cfg[i][0], cfg[i][1]);
    strobe(SRX);

    rx_q = xQueueCreate(4, sizeof(rmt_rx_done_event_data_t));
    rmt_channel_handle_t chan = NULL;
    rmt_rx_channel_config_t rxc = {
        .clk_src = RMT_CLK_SRC_DEFAULT, .resolution_hz = 1000000,
        .mem_block_symbols = 64, .gpio_num = PIN_GDO0,
    };
    ESP_ERROR_CHECK(rmt_new_rx_channel(&rxc, &chan));
    rmt_rx_event_callbacks_t cbs = { .on_recv_done = on_recv };
    ESP_ERROR_CHECK(rmt_rx_register_event_callbacks(chan, &cbs, NULL));
    ESP_ERROR_CHECK(rmt_enable(chan));

    //several repeats per receive, so re-arming never cuts a frame
    static rmt_symbol_word_t sym[256];
    rmt_receive_config_t rc = { .signal_range_min_ns = 1000,
                                .signal_range_max_ns = 8000000 };   //8 ms ends a burst
    printf("listening for the fpga's clean retransmit (rmt)\n");
    ESP_ERROR_CHECK(rmt_receive(chan, sym, sizeof(sym), &rc));

    rmt_rx_done_event_data_t ev;
    while (1) {
        if (xQueueReceive(rx_q, &ev, portMAX_DELAY) == pdTRUE)
            decode_symbols(ev.received_symbols, ev.num_symbols);
        rmt_receive(chan, sym, sizeof(sym), &rc);
    }
}
