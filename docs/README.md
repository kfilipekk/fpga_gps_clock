# Docs

What is measured and how it is checked. Every figure is
measured on the board unless stated otherwise.

[Spec sheet](#spec-sheet) · [Measurements](#measurements) ·
[Verification](#verification) · [Reproduce](#reproduce)

## Spec Sheet

The carry-chain TDC and the clocks around it, on a Gowin GW1NR-9C (Tang
Nano 9K) with the open source flow.

| TDC | value | notes |
|---|---|---|
| clock | 27 MHz board crystal | -6.47 ppm against GPS |
| chain | 1200 ALU taps, 6 segments of 200 | [tdc_chain.v](../gpsdo/rtl/tdc_chain.v) |
| tap, median | 24.6 ps | 51,250 ring samples, 22.8 to 25.7 ps across placements |
| mean bin | 62 ps | ~600 codes span one 37 ns clock |
| DNL / INL | +89 / -1 LSB, 81 LSB peak | the segment hops, calibrated out by the LUT |
| single-shot quantisation | 837 ps rms | dominated by the wide hop bins |
| wave union | 778 → 575 ps quantisation | best single chain vs two summed, same edges |
| single-shot precision | ~31 ps rms per channel, 1.4 ns in a hop bin | one edge on two chains, 72k edges |
| dead time | 44 µs | the snapshot shifts out one tap a clock |
| calibration | ring oscillator code density | no GPS or external source |

| Instruments | value | notes |
|---|---|---|
| time interval counter | 2 channels, 32-bit coarse (159 s range) | 43% LUT, 38% ALU, 126 MHz |
| Allan deviation, 1 s | 11.2 ppb with the TDC, 21.2 ppb count only | 1,899 s run |
| Allan deviation floor | 2.65 ppb at 8 to 16 s | crystal wander above ~30 s |
| GPS PPS jitter | 6.5 ns rms per edge | NEO-M8N sawtooth |
| frequency transfer | CC1101 carrier to ±0.21 Hz at 433.92 MHz, 300 s | [xocal](../extras/xocal/README.md) |
| radio packet stamp | per-packet UTC, to one 37 ns clock for now | [radio433](../extras/radio433/README.md) |

Limits:

- The hops dominate. A third of edges land in a 4 to 6 ns hop bin, and
  wave union only shrinks a hop where the other chain's taps are fine.
- In the two-channel build one chain reads a clock late and saturates a
  third of the time. The cause is unconfirmed
  ([ticprec](../extras/ticprec/README.md)).
- 1 s stability is set by the GPS pulse (6.5 ns), not the TDC (~30 ps).
- The discipline loop is proven in simulation only, until a VCTCXO is
  wired.

## Measurements

### TDC Tap Linearity

![tdc code density](img/tdc-code-density.png)

The gpsdo bitstream in ring oscillator calibration mode (S1). The ring is
asynchronous to the crystal, so its edges land evenly over the 37 ns clock
period, and a histogram of where they land gives the width of every tap.
The spikes are the segment hops at taps 0, 200 and 400, where the carry
crosses a fabric column and one tap covers ~5 ns. The per-tap table is the
calibration LUT: raw code in, picoseconds out.

### Allan Deviation, Count vs TDC

![pps allan deviation](img/pps-adev.png)

1,899 s of unbroken GPS PPS, then 60,081 ring samples in the same capture,
so the LUT is taken minutes after the PPS it corrects. Each interval is the
clock count less this edge's tap delay plus the last one's.

| τ | count only | count + TDC |
|---|---|---|
| 1 s | 21.2 ppb | **11.2 ppb** |
| 4 s | 5.6 ppb | 3.1 ppb |
| 16 s | 3.1 ppb | **2.65 ppb** |
| 64 s | 4.2 ppb | 4.2 ppb |
| 512 s | 18.3 ppb | 18.3 ppb |

The TDC halves the 1 s figure, and what is left is the GPS. The TDC's own
quantisation is 1.2 ppb on a 1 s interval, while the M8N's pulse jitters
6.5 ns rms per edge. That fits the sawtooth of the receiver snapping its
pulse to its own clock (a uniform ±10.4 ns would give 6.0 ns).
UBX-TIM-TP qErr reports that offset for each pulse, so subtracting it is
the next improvement. Past ~30 s the curves merge and climb as the crystal
warms and wanders, which is what the discipline loop and a VCTCXO are for.

## Verification

CI runs lint, simulation, formal, a bitstream per design and the host
tests on every push.

| Layer | What | How |
|---|---|---|
| lint | verilator -Wall on every top and library module | `make lint` |
| simulation | 48 cocotb tests over 29 RTL modules, all but the two silicon-only delay lines | `make sim` |
| formal | SymbiYosys, two unbounded proofs and one bounded check | `make formal` |
| upsets | bit flip campaign on the discipline loop | `make -C gpsdo/sim disc_loop_seu disc_loop_seu_tmr` |
| host | 45 tests on the analysis code, synthetic captures with known answers | `python3 */host/test_*.py` |

- **uart_tx, proved.** Every accepted byte comes out as start, 8 data bits
  LSB first and stop, DIV clocks each, idle high otherwise. k-induction.
- **spi_cfg, proved.** SPI mode 0 for any MISO, mode and start: SCK is low
  whenever CSN is high, MOSI never changes on the clock SCK rises, and done
  is only raised with the chip deselected. Induction needed per-state
  invariants inside the module.
- **uart_tx into uart_rx, bounded.** Every byte sent comes out once,
  unchanged, and nothing comes out that was not sent. 160 clocks, four
  back-to-back frames.

Each property was checked against a planted bug first (MSB-first TX, MOSI
moving with SCK, MSB-first RX), and all three fail.

**Upsets.** 200 random bit flips in the locked loop: 130 leave the plain
loop out of lock, none the triplicated one
([gpsdo](../gpsdo/README.md#single-event-upsets)).

**What simulation cannot see.** The carry chains and ring oscillator are
zero-delay stubs in simulation and are characterised on silicon. That gap
showed twice: a TDC trigger change passed every test and hung on the
board, and the TMR merge only showed in the synthesis stats.

## Reproduce

    stty -F /dev/ttyUSB1 115200 raw -echo

    #tdc code density, gpsdo bitstream in s1 calibration mode
    timeout 60 cat /dev/ttyUSB1 > taps.txt
    python3 gpsdo/host/tdc_cal.py taps.txt

    #allan deviation, gpsdo bitstream: ~30 min of pps, then s1 for a minute
    python3 gpsdo/host/pps_adev.py run.txt --png adev.png

    #single-shot precision, ticprec bitstream, no wiring
    python3 extras/ticprec/host/tic_prec.py tic.txt --png precision.png
