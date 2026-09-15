# xocal

Measures a CC1101 module's 26 MHz crystal against GPS, which gives the
radio's absolute carrier frequency with no spectrum analyser or SDR. The
carrier is a fixed multiple of the crystal, f = FREQ × f_xo / 2^16, so
the crystal error is the carrier error.

## How

spi_cfg writes IOCFG0 = 0x3F, which puts the crystal divided by 192
(~135 kHz) out on GDO0, the pin already wired to the FPGA. xo_meter is a
reciprocal counter: it times whole GDO0 periods against the 27 MHz clock,
from the first GDO0 edge after one PPS to the first after the next.
pps_capture counts the clock over the same GPS second, so each second

    f_xo = 192 × m / c × p

and one line comes out of the UART, `XMMMMMMMM CCCCCCCC PPPPPPPP`.

Each window is off by at most a clock at either end, and consecutive
windows share their boundary edges, so summing a run telescopes: the error
is two clocks over the whole span, not per line. 124 s gives ±0.26 Hz at
433.92 MHz. With no PPS for 1.5 s it gates itself every 27e6 clocks and p
reads 0; the host then assumes the board crystal's last GPS-measured
-6.25 ppm and flags the result as not traceable.

## Use

    make -C extras/xocal flash
    cat /dev/ttyUSB1 | python3 extras/xocal/host/xocal.py

Same wiring as [radio433](../radio433/README.md). LED 0 lit means the
CC1101 is configured, LED 1 lit means PPS is present, LED 5 toggles per
line.

## Measured

The FPGA's own CC1101, 300 s against GPS PPS, no dropouts:

    xo                25,997,839.6 Hz   -83.09 ppm
    433.92 carrier    -36,225 Hz        (±0.21 Hz)
    corrected FREQ    0x10B0CC (was 0x10B071), leaves -126 Hz

-83 ppm is far outside a normal crystal spec, probably a module with the
wrong load capacitors, and it puts the carrier a sixth of the way across
the 203 kHz RX filter. The FREQ word steps in f_xo / 2^16 = 397 Hz, so the
best a word can do is ±198 Hz, while the measurement places the carrier to
under a hertz.

The ±0.21 Hz is the counting. The crystal itself moves more: it warmed
from -83.15 to -83.09 ppm over the 300 s, and an earlier run read 60 Hz
lower. That wander of tens of Hz over minutes sets the floor for Doppler
work with this radio.

## Retuning Radio433

radio433_top takes the word as CC_FREQ, by default the nominal 0x10B071:

    make -C extras/radio433 PARAMS="chparam -set CC_FREQ 1093836 radio433_top"

It stays nominal. Alternating 2 minute runs of each word decoded 12, 7, 9
and 22 beacon bursts (nominal, retuned, nominal, retuned), well within
chance: at 203 kHz the RX filter barely notices a 36 kHz shift. The word
matters once the filter is narrowed for sensitivity.
