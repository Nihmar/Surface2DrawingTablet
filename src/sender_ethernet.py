#!/usr/bin/env python3
import evdev, socket, struct, subprocess, time

# ─── CONFIGURATION ────────────────────────────────────────────
PEN_DEVICE_NAME = "IPTSD Virtual Stylus"  # update if your device name differs
HOST_IP         = "10.0.0.2"              # static IP of the host PC (direct Ethernet)
PORT            = 5005
BACKLIGHT       = "/sys/class/backlight/intel_backlight/brightness"
ETHERNET_IFACE  = "enp0s20f0u1"           # USB-Ethernet adapter interface name on the Surface
                                           # check yours with: ip link show
# ──────────────────────────────────────────────────────────────

def set_brightness(value):
    subprocess.run(
        ["tee", BACKLIGHT],
        input=str(value).encode(),
        stdout=subprocess.DEVNULL
    )

def setup_ethernet():
    """Assign static IP to the direct Ethernet interface."""
    subprocess.run(["ip", "addr", "add", "10.0.0.1/24", "dev", ETHERNET_IFACE], check=False)
    subprocess.run(["ip", "link", "set", ETHERNET_IFACE, "up"], check=True)
    print(f"Ethernet interface {ETHERNET_IFACE} configured as 10.0.0.1")

def find_pen_device():
    """Find the pen device by name. Retries until found."""
    while True:
        for path in evdev.list_devices():
            try:
                dev = evdev.InputDevice(path)
                if PEN_DEVICE_NAME in dev.name:
                    print(f"Pen device found: {dev.path} ({dev.name})")
                    return dev
            except Exception:
                continue
        print("Pen device not found, retrying in 1s...")
        time.sleep(1)

setup_ethernet()

# Save current brightness to restore on exit
with open(BACKLIGHT) as f:
    original_brightness = f.read().strip()

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # disable Nagle's algorithm
sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)  # small send buffer = fast flush
sock.connect((HOST_IP, PORT))
print(f"Connected to {HOST_IP}:{PORT}")

set_brightness(0)
print("Screen off. Press Ctrl+C to quit.")

try:
    while True:
        dev = find_pen_device()
        try:
            dev.grab()
            for event in dev.read_loop():
                data = struct.pack("hhi", event.type, event.code, event.value)
                sock.sendall(data)
        except OSError as ex:
            print(f"Device lost ({ex}), reconnecting...")
            try:
                dev.ungrab()
            except OSError:
                pass  # device already gone, ignore
            time.sleep(1)  # wait for device to be re-enumerated
except KeyboardInterrupt:
    pass
finally:
    set_brightness(original_brightness)
    print(f"Screen restored (brightness: {original_brightness})")
    try:
        dev.ungrab()
    except OSError:
        pass
    sock.close()
