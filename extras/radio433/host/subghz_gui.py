#!/usr/bin/env python3
#dashboard for the radio node
#~/subghz-venv/bin/python subghz_gui.py [/dev/ttyUSB1]

import os
import re
import subprocess
import sys
import threading
import time
from collections import Counter, deque

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, os.path.join(REPO, "gpsdo/host"))

from ook_decode import parse, nexus, classify
from subghz import fingerprint
from tdc_cal import characterise
from timing import NOMINAL, freq_error_ppb, allan_dev
from nicegui import ui

FPGA = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB1"
ESP = "/dev/ttyACM0"
DIRS = {"gpsdo": "gpsdo", "radio433": "extras/radio433"}
CAPDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captures")
MIN_SEEN = 3
CLK_HZ = 27e6
TAP_PS = 43            #rough ps per tap, for display only
OUR_ID = 0xA3          #the esp node, humidity field is its sound level
GPSDO_RE = re.compile(r"^([0-9A-Fa-f]{8}) ([0-9A-Fa-f]{3})$")

devs = {}
sensors = {}
events = deque(maxlen=250)
wall = deque(maxlen=400)
fine_hist = deque(maxlen=8000)
periods = deque(maxlen=4000)
decode_wall = deque(maxlen=300)
state = {"gpsdo_last": 0.0, "flash": "", "show_noise": False}
lock = threading.Lock()


def decode(short, long, bits):
    if 22 <= len(bits) <= 28 and long >= short * 2.2:
        v = int(bits[:24].ljust(24, "0"), 2)
        return "EV1527 / PT2262", f"id {v >> 4:05X}   btn {v & 0xF:X}"
    if len(bits) >= 8:
        return "raw ook", f"{len(bits)} bits"
    return "unknown", "-"


def fmt_time(sec, sub):
    usec = sub / (CLK_HZ / 1e6)
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}.{int(usec):06d}"


def on_radio(pkt, now):
    nx = nexus(pkt["runs"])
    fp = None if nx else fingerprint(pkt["runs"])
    cl = None if nx else classify(pkt["runs"])
    with lock:
        wall.append(now)
        fine_hist.append(pkt["fine"])
        events.append({"sec": pkt["sec"], "sub": pkt["sub"], "fine": pkt["fine"],
                       "key": fp[0] if fp else None, "dec": pkt.get("dec"),
                       "nruns": len(pkt["runs"]),
                       "coding": (cl["coding"] if cl and cl["coding"] != "unknown" else None),
                       "cksum": (cl["checksum"] if cl else None),
                       "nbits": (cl["nbits"] if cl else 0),
                       "nexus": (None if not nx else
                                 f'{nx["temp_c"]:.1f}C sound {nx["humidity"]}'
                                 if nx["id"] == OUR_ID else
                                 f'{nx["temp_c"]:.1f}C {nx["humidity"]}% rh')})
        if nx:
            decode_wall.append(now)
            s = sensors.setdefault((nx["model"], nx["id"]), {"seen": 0, "hist": deque(maxlen=60)})
            s.update(nx)
            s["seen"] += 1
            s["wall"] = now
            s["sec"], s["sub"], s["fine"] = pkt["sec"], pkt["sub"], pkt["fine"]
            s["hist"].append((now, nx["temp_c"]))
            return
        if not fp:
            return
        key, bits = fp
        d = devs.setdefault(key, {"seen": 0, "bits": "", "fixed": False, "rep": 0,
                                  "hist": deque(maxlen=30)})
        d["rep"] = d["rep"] + 1 if bits == d["bits"] else 0
        d["fixed"] = d["fixed"] or d["rep"] >= 2
        d["seen"] += 1
        d["bits"] = bits
        d["short"], d["long"] = key
        d["runs"] = [[lvl, round(w / 27)] for lvl, w in pkt["runs"]]
        d["sec"], d["sub"], d["fine"] = pkt["sec"], pkt["sub"], pkt["fine"]
        d["wall"] = now
        d["hist"].append(now)
        d["proto"], d["info"] = decode(key[0], key[1], bits)


def on_gpsdo(period, fine, now):
    with lock:
        wall.append(now)
        if fine:                       #radio433 sends 000
            fine_hist.append(fine)
        periods.append((now, period))
        state["gpsdo_last"] = now


def reader():
    os.system(f"stty -F {FPGA} 115200 raw -echo")
    while True:
        pkt = None
        try:
            with open(FPGA, "r", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    now = time.time()
                    try:
                        if line.startswith("@"):
                            if pkt:
                                on_radio(pkt, now)
                            p = line[1:].split()
                            pkt = {"sec": int(p[0], 16), "sub": int(p[1], 16),
                                   "fine": int(p[2], 16), "runs": []}
                        elif line.startswith("R") and pkt is not None and len(line) == 8:
                            pkt["runs"].append((int(line[1]), int(line[2:8], 16)))
                        elif line.startswith("D") and pkt is not None and len(line) >= 3:
                            pkt["dec"] = line[1:]
                        else:
                            m = GPSDO_RE.match(line)
                            if m:
                                on_gpsdo(int(m.group(1), 16), int(m.group(2), 16), now)
                    except (ValueError, IndexError):
                        continue
        except Exception:
            time.sleep(1)


def transmit(runs):
    r = list(runs)
    while r and r[0][0] != 1:
        r = r[1:]
    durs = ",".join(str(max(1, int(u))) for _lvl, u in r)
    os.system(f"stty -F {ESP} 115200 raw -echo")
    try:
        with open(ESP, "w") as f:
            f.write("P" + durs + "\n")
            f.flush()
        ui.notify("replayed through the esp", color="purple")
    except Exception as e:
        ui.notify(f"esp not ready: {e}", color="red")


def pulse_strip(runs):
    cells = "".join(
        f'<div style="flex:{max(1, w)};background:{"#a78bfa" if lvl else "#2a2440"}"></div>'
        for lvl, w in runs[:80])
    return (f'<div style="display:flex;height:22px;border-radius:5px;'
            f'overflow:hidden;width:100%">{cells}</div>')


def sparkline(hist, colour="#a78bfa"):
    vals = [t for _w, t in hist]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1
    pts = " ".join(f"{i * 100 / (len(vals) - 1):.1f},{22 - (v - lo) / rng * 20:.1f}"
                   for i, v in enumerate(vals))
    return (f'<svg viewBox="0 0 100 24" width="100%" height="34" preserveAspectRatio="none">'
            f'<polyline points="{pts}" fill="none" stroke="{colour}" stroke-width="1.2"/></svg>')


def rate_hz():
    with lock:
        w = [t for t in wall if t > time.time() - 5]
    return len(w) / 5.0


def decode_stats():
    #decodes in the last 30 s, and seconds since the last one
    now = time.time()
    with lock:
        dw = list(decode_wall)
    per_min = round(len([t for t in dw if t > now - 30]) * 2)
    since = (now - dw[-1]) if dw else None
    return per_min, since


def link_state(since):
    if since is None:
        return "grey", "no signal yet"
    if since < 2:
        return "green", "live"
    if since < 6:
        return "amber", "weak"
    return "grey", f"missed · {since:.0f}s ago"


@ui.refreshable
def stats_bar():
    with lock:
        ev = list(events)
        n_dev = sum(1 for d in devs.values() if d["seen"] >= MIN_SEEN)
        n_sen = len(sensors)
        up = max((e["sec"] for e in ev), default=0)
    n_noise = sum(1 for e in ev if is_noise(e))
    pps = "yes" if time.time() - state["gpsdo_last"] < 2 else "no"
    per_min, since = decode_stats()
    dcol, _ = link_state(since)
    cards = [("decoded/min", f"{per_min}", dcol),
             ("signals", f"{len(ev) - n_noise}", "purple"), ("sensors", f"{n_sen}", "purple"),
             ("devices", f"{n_dev}", "purple"), ("noise", f"{n_noise}", "grey"),
             ("pps", pps, "purple" if pps == "yes" else "grey"),
             ("uptime", f"{up // 60}m{up % 60:02d}s", "grey")]
    with ui.row().classes("w-full gap-2 no-wrap"):
        for lbl, val, col in cards:
            with ui.card().classes("flex-1 items-center py-1").style("background:#161320"):
                ui.label(val).classes(f"text-lg text-bold text-{col}")
                ui.label(lbl).classes("text-xs text-grey")


DOT = {"green": "#22c55e", "amber": "#f59e0b", "grey": "#6b7280"}


@ui.refreshable
def sensors_panel():
    with lock:
        snap = [dict(s) for s in sorted(sensors.values(), key=lambda x: -x["seen"])]
    per_min, since = decode_stats()
    if not snap:
        _, txt = link_state(since)
        ui.label(f"waiting for the esp beacon, {txt}").classes("text-grey")
        return
    with ui.row().classes("w-full gap-3 no-wrap"):
        for s in snap:
            ago = time.time() - s["wall"]
            mine = s["id"] == OUR_ID
            col, txt = link_state(ago) if mine else ("green", "live")
            with ui.card().classes("flex-1 py-2 gap-1").style("background:#161320;border:1px solid #2a2440"):
                with ui.row().classes("items-center w-full no-wrap gap-2"):
                    ui.html(f'<span style="color:{DOT[col]}">●</span>')
                    ui.label(f'{"ESP32-S3 Sense" if mine else s["model"]}  0x{s["id"]:02X}').classes("text-purple text-bold")
                    ui.space()
                    ui.label(f'{txt} · {per_min}/min' if mine else txt).classes("text-caption text-grey")
                with ui.row().classes("items-baseline gap-3 no-wrap"):
                    ui.label(f'{s["temp_c"]:.1f}°C').classes("text-h4 text-white")
                    ui.label(f'sound {s["humidity"]}' if mine
                             else f'{s["humidity"]}% rh').classes("text-subtitle1 text-purple")
                ui.html(sparkline(s["hist"]))
                ui.label(f'ch{s["channel"]} · batt {"ok" if s["battery"] else "low"} · x{s["seen"]} · '
                         f'{fmt_time(s["sec"], s["sub"])} +{s["fine"]}t').style(
                    "font-family:monospace").classes("text-caption text-grey")


def is_noise(e):
    #a passing checksum is never noise
    return (e["key"] is None and not e["nexus"] and not e["dec"]
            and not e.get("cksum"))


def stream_rows():
    with lock:
        evs = list(events)[::-1]
        show = state["show_noise"]
    rows = []
    for e in evs:
        if is_noise(e) and not show:
            continue
        kind = ("SENSOR" if e["nexus"] else "DECODE" if e["dec"]
                else "dev" if e["key"] else "coded" if e.get("cksum")
                else "signal" if e.get("coding") else "noise")
        fp = f'{e["key"][0]}/{e["key"][1]}us' if e["key"] else f'{e["nruns"]} runs'
        info = e["nexus"] or (f'0x{e["dec"]}' if e["dec"] else "")
        if not info and e.get("coding"):
            info = f'{e["coding"]} {e["nbits"]}b' + (f' crc:{e["cksum"]}' if e.get("cksum") else "")
        rows.append({"t": fmt_time(e["sec"], e["sub"]),
                     "tdc": f'+{e["fine"]} taps  ~{e["fine"] * TAP_PS / 1000:.1f} ns',
                     "fp": fp, "kind": kind, "info": info})
        if len(rows) >= 40:
            break
    return rows


@ui.refreshable
def device_list():
    with lock:
        snap = [dict(d) for d in sorted(
            (x for x in devs.values() if x["seen"] >= MIN_SEEN), key=lambda x: -x["seen"])]
    if not snap:
        ui.label("listening... repeating fixed-code devices appear here").classes("text-grey")
        return
    for d in snap:
        h = list(d["hist"])
        iv = (h[-1] - h[0]) / (len(h) - 1) if len(h) > 1 else 0
        ago = time.time() - d["wall"]
        with ui.card().classes("w-full").style("background:#1a1626"):
            with ui.row().classes("items-center w-full no-wrap"):
                ui.label(f'{d["short"]}/{d["long"]} us').style("font-family:monospace").classes("text-purple")
                ui.label(f'x{d["seen"]}').classes("text-grey")
                if d["fixed"]:
                    ui.badge("FIXED - clonable").props("color=purple")
                ui.label(d["proto"]).classes("text-purple")
                ui.label(d["info"]).style("font-family:monospace").classes("text-white")
                ui.space()
                ui.button("replay", icon="wifi_tethering",
                          on_click=lambda r=d["runs"]: transmit(r)).props("color=purple dense")
            ui.html(pulse_strip(d["runs"]))
            with ui.row().classes("w-full no-wrap text-caption text-grey gap-4"):
                ui.label(f'tdc +{d["fine"]} taps (~{d["fine"] * TAP_PS / 1000:.1f} ns)')
                ui.label(f'every ~{iv:.1f}s' if iv else "")
                ui.label(f'{ago:.0f}s ago')


DARK_AXIS = {"axisLine": {"lineStyle": {"color": "#888"}},
             "splitLine": {"lineStyle": {"color": "#222"}}}


def tdc_hist_options():
    with lock:
        c = Counter(fine_hist)
        n = len(fine_hist)
    if not c:
        return None, 0
    lo, hi = min(c), max(c)
    xs = list(range(lo, hi + 1))
    ys = [c.get(x, 0) for x in xs]
    return {"title": {"text": "TDC code density (tap occupancy)", "textStyle": {"color": "#ccc", "fontSize": 13}},
            "tooltip": {}, "grid": {"left": 45, "right": 12, "top": 34, "bottom": 28},
            "xAxis": dict({"type": "category", "data": xs, "name": "tap code"}, **DARK_AXIS),
            "yAxis": dict({"type": "value", "name": "hits"}, **DARK_AXIS),
            "series": [{"type": "bar", "data": ys, "itemStyle": {"color": "#a78bfa"}}]}, n


def freq_options():
    with lock:
        pts = list(periods)[-600:]
    if len(pts) < 2:
        return None
    data = [[round(w - pts[0][0], 1), round(freq_error_ppb(p), 1)] for w, p in pts]
    return {"title": {"text": "clock frequency error vs GPS", "textStyle": {"color": "#ccc", "fontSize": 13}},
            "tooltip": {"trigger": "axis"}, "grid": {"left": 55, "right": 12, "top": 34, "bottom": 30},
            "xAxis": dict({"type": "value", "name": "s"}, **DARK_AXIS),
            "yAxis": dict({"type": "value", "name": "ppb"}, **DARK_AXIS),
            "series": [{"type": "line", "showSymbol": False, "data": data,
                        "itemStyle": {"color": "#a78bfa"}}]}


def allan_options():
    with lock:
        ys = [(p - NOMINAL) / NOMINAL for _w, p in periods]
    ad = allan_dev(ys)
    if len(ad) < 2:
        return None
    data = [[t, s] for t, s in ad if s > 0]
    return {"title": {"text": "Allan deviation σy(τ)", "textStyle": {"color": "#ccc", "fontSize": 13}},
            "tooltip": {"trigger": "axis"}, "grid": {"left": 60, "right": 14, "top": 34, "bottom": 34},
            "xAxis": dict({"type": "log", "name": "τ (s)"}, **DARK_AXIS),
            "yAxis": dict({"type": "log", "name": "σy"}, **DARK_AXIS),
            "series": [{"type": "line", "data": data, "itemStyle": {"color": "#a78bfa"},
                        "lineStyle": {"width": 2}}]}


@ui.refreshable
def tdc_cal_panel():
    with lock:
        vals = list(fine_hist)
    if len(vals) < 100:
        ui.label(f"calibrating... {len(vals)} tap samples (widest spread: gpsdo ring-osc cal mode)").classes(
            "text-caption text-grey")
        return
    s = characterise(vals, CLK_HZ)
    cards = [("samples", f"{s['total']}", "purple"),
             ("codes", f"{s['populated']} of {s['nbins']}", "purple"),
             ("median tap", f"{s['median']:.1f} ps", "purple"),
             ("dnl", f"+{s['dnl_max']:.1f} / {s['dnl_min']:.1f} lsb", "purple"),
             ("inl peak", f"{s['inl_max']:.1f} lsb", "purple"),
             ("sigma", f"{s['sigma']:.1f} ps", "purple")]
    with ui.row().classes("w-full gap-2 no-wrap"):
        for lbl, val, col in cards:
            with ui.card().classes("flex-1 items-center py-2").style("background:#161320"):
                ui.label(val).classes(f"text-lg text-bold text-{col}")
                ui.label(lbl).classes("text-xs text-grey")


@ui.refreshable
def timing_status():
    with lock:
        pts = list(periods)[-30:]
        n = len(fine_hist)
    present = time.time() - state["gpsdo_last"] < 2 and len(pts) > 0
    if present:
        errs = [freq_error_ppb(p) for _w, p in pts]
        mean = sum(errs) / len(errs)
        std = (sum((e - mean) ** 2 for e in errs) / len(errs)) ** 0.5
        cards = [("pps", "TRACKING", "purple"), ("freq error", f"{mean:+.0f} ppb", "purple"),
                 ("1s stability", f"{std:.0f} ppb", "purple"), ("tdc samples", f"{n}", "purple")]
    else:
        cards = [("pps", "no gpsdo telemetry", "grey"),
                 ("tdc samples", f"{n}", "purple"),
                 ("hint", "flash the gpsdo bitstream (Control tab) for discipline", "grey")]
    with ui.row().classes("w-full gap-2 no-wrap"):
        for lbl, val, col in cards:
            with ui.card().classes("flex-1 items-center py-2").style("background:#161320"):
                ui.label(val).classes(f"text-lg text-bold text-{col}")
                ui.label(lbl).classes("text-xs text-grey")


def flash_bitstream(proj):
    def run():
        cmd = (f"cd {REPO}/{DIRS[proj]} && source {REPO}/tools/oss-cad-suite/environment "
               f"&& make flash-persist")
        r = subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True)
        ok = "CRC check: Success" in r.stdout
        with lock:
            state["flash"] = (f"{proj}: flashed ok - REPLUG the FPGA USB to boot it"
                              if ok else f"{proj}: flash failed (see terminal)")
    with lock:
        state["flash"] = f"flashing {proj}... (this takes ~1 min)"
    threading.Thread(target=run, daemon=True).start()


def captures():
    try:
        return sorted(f for f in os.listdir(CAPDIR) if f.endswith(".json"))
    except FileNotFoundError:
        return []


def replay_capture(name):
    import json
    cap = json.load(open(os.path.join(CAPDIR, name)))
    transmit(cap["runs"])


def fpga_retransmit():
    try:
        with open(FPGA, "w") as f:
            f.write("T\n")
            f.flush()
        ui.notify("fpga retransmitting last capture", color="purple")
    except Exception as e:
        ui.notify(f"fpga not ready: {e}", color="red")


def fpga_transcode():
    try:
        with open(FPGA, "w") as f:
            f.write("C\n")
            f.flush()
        ui.notify("fpga transcoding last nexus frame", color="purple")
    except Exception as e:
        ui.notify(f"fpga not ready: {e}", color="red")


@ui.page("/")
def index():
    ui.dark_mode(True)
    with ui.row().classes("items-center w-full"):
        ui.icon("radar").classes("text-3xl text-purple")
        ui.label("gps-disciplined radio node").classes("text-h5 text-bold")
        ui.space()
        ui.label(f"fpga {FPGA}  ·  esp {ESP}").classes("text-grey text-caption")
    stats_bar()
    ui.timer(1.0, stats_bar.refresh)

    with ui.tabs().classes("w-full") as tabs:
        t_radio = ui.tab("Radio", icon="settings_input_antenna")
        t_time = ui.tab("Timing", icon="schedule")
        t_ctrl = ui.tab("Control", icon="tune")
    with ui.tab_panels(tabs, value=t_radio).classes("w-full").style("background:transparent"):
        with ui.tab_panel(t_radio):
            ui.label("decoded sensors").classes("text-subtitle1 text-bold")
            ui.label("live sensor readings demodulated in fabric, stamped with gps time").classes("text-caption text-grey")
            sensors_panel()
            ui.separator()
            with ui.row().classes("w-full no-wrap gap-4 items-start"):
                with ui.column().classes("w-1/2"):
                    with ui.row().classes("items-center w-full no-wrap"):
                        ui.label("live packet stream").classes("text-subtitle1 text-bold")
                        ui.space()
                        ui.switch("show noise", value=state["show_noise"],
                                  on_change=lambda e: state.update(show_noise=e.value)).props("dense color=purple")
                    cols = [{"name": "t", "label": "arrival (h:m:s.µs)", "field": "t", "align": "left"},
                            {"name": "tdc", "label": "tdc sub-cycle", "field": "tdc", "align": "left"},
                            {"name": "fp", "label": "fingerprint", "field": "fp", "align": "left"},
                            {"name": "kind", "label": "type", "field": "kind", "align": "left"},
                            {"name": "info", "label": "payload", "field": "info", "align": "left"}]
                    tbl = ui.table(columns=cols, rows=[], row_key="t").classes("w-full").props("dense flat")
                    tbl.style("background:#161320;font-family:monospace")
                    ui.timer(0.6, lambda: tbl.update_rows(stream_rows()))
                with ui.column().classes("w-1/2"):
                    ui.label("devices (fixed-code = clonable)").classes("text-subtitle1 text-bold")
                    device_list()
            ui.timer(1.0, lambda: (sensors_panel.refresh(), device_list.refresh()))

        with ui.tab_panel(t_time):
            ui.label("timing instruments").classes("text-subtitle1 text-bold")
            ui.label("the picosecond core: tap linearity, clock discipline, stability").classes("text-caption text-grey")
            timing_status()
            tdc_cal_panel()
            tdc_chart = ui.echart({}).classes("w-full").style("height:240px")
            with ui.row().classes("w-full no-wrap gap-4"):
                freq_chart = ui.echart({}).classes("w-1/2").style("height:240px")
                allan_chart = ui.echart({}).classes("w-1/2").style("height:240px")

            def upd():
                timing_status.refresh()
                tdc_cal_panel.refresh()
                o, _ = tdc_hist_options()
                if o:
                    tdc_chart.options.clear(); tdc_chart.options.update(o); tdc_chart.update()
                for chart, fn in ((freq_chart, freq_options), (allan_chart, allan_options)):
                    o = fn()
                    if o:
                        chart.options.clear(); chart.options.update(o); chart.update()
            ui.timer(1.5, upd)

        with ui.tab_panel(t_ctrl):
            ui.label("transmitter / replay").classes("text-subtitle1 text-bold")
            ui.label("send a saved capture through the esp cc1101 (your own devices only)").classes("text-caption text-grey")
            caps = captures()
            sel = ui.select(caps, value=caps[0] if caps else None).classes("w-96") if caps else None
            if sel:
                ui.button("replay through esp", icon="wifi_tethering",
                          on_click=lambda: replay_capture(sel.value)).props("color=purple")
            else:
                ui.label("no captures saved yet (host/captures/)").classes("text-grey")
            ui.separator()
            ui.label("fpga retransmit").classes("text-subtitle1 text-bold")
            ui.label("the fpga's own cc1101 re-sends the last captured packet (host 'T' over uart)").classes(
                "text-caption text-grey")
            with ui.row():
                ui.button("retransmit last capture (fpga)", icon="wifi_tethering",
                          on_click=fpga_retransmit).props("color=purple")
                ui.button("transcode nexus frame (clean)", icon="auto_fix_high",
                          on_click=fpga_transcode).props("color=purple outline")
            ui.separator()
            ui.label("bitstream").classes("text-subtitle1 text-bold")
            ui.label("one bitstream runs at a time; flashing writes SPI flash, then replug to boot").classes("text-caption text-grey")
            with ui.row():
                ui.button("flash radio433 (rx + decode)", icon="cell_tower",
                          on_click=lambda: flash_bitstream("radio433")).props("color=purple")
                ui.button("flash gpsdo (discipline + telemetry)", icon="schedule",
                          on_click=lambda: flash_bitstream("gpsdo")).props("color=amber")
            flash_lbl = ui.label("").classes("text-caption text-purple")
            ui.timer(1.0, lambda: flash_lbl.set_text(state["flash"]))


if __name__ in {"__main__", "__mp_main__"}:
    threading.Thread(target=reader, daemon=True).start()
    ui.run(port=8433, show=False, reload=False, title="gps-disciplined radio node")
