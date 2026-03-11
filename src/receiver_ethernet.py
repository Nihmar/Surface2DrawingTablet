#!/usr/bin/env python3
import socket, struct, subprocess
from evdev import UInput, AbsInfo, ecodes as e

# ─── CONFIGURATION ────────────────────────────────────────────
PORT           = 5005
ETHERNET_IFACE = "enp0s1"   # interface connected to the Surface
                              # check yours with: ip link show
# Adapt these values to your Surface by running:
#   sudo evtest /dev/input/eventX   (on the Surface, select the Stylus device)
# and reading the Min/Max/Fuzz/Resolution for each ABS_* axis.
ABS_X_MAX    = 44800
ABS_Y_MAX    = 29920
ABS_PRES_MAX = 4096
ABS_TILT_MIN = -9000
ABS_TILT_MAX =  9000
# ──────────────────────────────────────────────────────────────

def setup_ethernet():
    """Assign static IP to the direct Ethernet interface."""
    subprocess.run(["ip", "addr", "add", "10.0.0.2/24", "dev", ETHERNET_IFACE], check=False)
    subprocess.run(["ip", "link", "set", ETHERNET_IFACE, "up"], check=True)
    print(f"Ethernet interface {ETHERNET_IFACE} configured as 10.0.0.2")

setup_ethernet()

cap = {
    e.EV_KEY: [
        e.BTN_TOOL_PEN,
        e.BTN_TOOL_RUBBER,
        e.BTN_TOUCH,
        e.BTN_STYLUS,
        e.BTN_STYLUS2,
    ],
    e.EV_ABS: [
        (e.ABS_X,        AbsInfo(0, 0, ABS_X_MAX,    4, 0, 200)),
        (e.ABS_Y,        AbsInfo(0, 0, ABS_Y_MAX,    4, 0, 200)),
        (e.ABS_PRESSURE, AbsInfo(0, 0, ABS_PRES_MAX, 0, 0, 0)),
        (e.ABS_TILT_X,   AbsInfo(0, ABS_TILT_MIN, ABS_TILT_MAX, 0, 0, 0)),
        (e.ABS_TILT_Y,   AbsInfo(0, ABS_TILT_MIN, ABS_TILT_MAX, 0, 0, 0)),
    ],
}

ui = UInput(cap, name="Surface Pen Virtual", vendor=0x045e, product=0x0021)
print("Virtual tablet device created")

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("0.0.0.0", PORT))
server.listen(1)
print(f"Listening on port {PORT}...")

conn, addr = server.accept()
print(f"Surface connected from {addr}")

try:
    while True:
        data = conn.recv(8)
        if not data or len(data) < 8:
            break
        etype, code, value = struct.unpack("hhi", data)
        ui.write(etype, code, value)
        if etype == e.EV_SYN:
            ui.syn()
except (ConnectionResetError, KeyboardInterrupt):
    pass
finally:
    conn.close()
    ui.close()
    server.close()
    print("Receiver closed.")
