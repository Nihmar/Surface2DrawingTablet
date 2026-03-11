# Surface2DrawingTablet

Use a **Surface Pro 6 running Arch Linux** as a wireless or wired external drawing tablet (screen off) connected to a second PC, via evdev event forwarding over the network.

```
┌────────────────────────────────┐         TCP/UDP          ┌───────────────────────────────────────────┐
│   Surface Pro 6                │ ───────────────────────▶ │     Host PC                               │
│   (sender)                     │  WiFi or direct Ethernet │   (receiver)                              │
│                                │                          │                                           │
│  pen events ──▶ Python script  │                          │  Python script ──▶ virtual uinput device  │
│  screen off                    │                          │  GNOME sees it as Wacom tablet            │
└────────────────────────────────┘                          └───────────────────────────────────────────┘
```

---

## Prerequisites

### On both machines
- Arch Linux
- Python 3 with `evdev`:
  ```bash
  pip install evdev
  ```

### On the Surface (sender)
- **linux-surface** kernel: [github.com/linux-surface/linux-surface](https://github.com/linux-surface/linux-surface)
- `iptsd` installed from AUR:
  ```bash
  yay -S iptsd
  ```

### On the host PC (receiver)
- Access to `/dev/uinput` (requires root or `uinput` group)

---

## 1. Enabling the pen driver on the Surface

The Surface Pro 6 uses the **ITHC** (Intel Touch Host Controller). The kernel module must be loaded manually.

```bash
sudo modprobe ithc
```

Verify it worked:
```bash
sudo dmesg | tail -20
```

You should see:
```
IPTSD Virtual Touchscreen 045E:001F → inputX
IPTSD Virtual Stylus 045E:001F      → inputY
```

Make it load automatically at boot:
```bash
echo "ithc" | sudo tee /etc/modules-load.d/ithc.conf
```

---

## 2. Identifying the pen input device

The scripts find the pen device **by name** automatically, so you don't need to hardcode a path. Just verify the name matches:

```bash
grep -r "Stylus\|stylus" /sys/class/input/*/name
```

It should return something like:
```
/sys/class/input/input12/name:IPTSD Virtual Stylus 045E:001F
```

The default name used in the scripts is `IPTSD Virtual Stylus`. If yours differs, update `PEN_DEVICE_NAME` in the sender script.

### Verify the device receives events
```bash
sudo evtest
```

Select the Stylus device, hover the pen — you should see `ABS_X`, `ABS_Y`, `ABS_PRESSURE` events streaming.

Take note of the **Max** values for each `ABS_*` axis and update them in the receiver script.

> **Tip:** if evtest shows no events, try from a separate TTY (`Ctrl+Alt+F2`) as the Wayland compositor may hold exclusive access.

---

## 3. Input device permissions

To run the sender without sudo:
```bash
sudo usermod -aG input $USER
newgrp input
```

---

## 4. Connection options

### Option A — WiFi
The simplest setup. Both machines connect to the same local network. Latency is typically 2–10ms on WiFi 5/6.

Use scripts: `sender_wifi.py` + `receiver_wifi.py`

### Option B — Direct Ethernet (recommended)
Connect a **USB-A → Ethernet adapter** to the Surface, then run a single Ethernet cable directly between the two machines. Modern NICs handle crossover automatically — no special cable needed.

Assign static IPs on both machines (replace interface names with yours from `ip link show`):

**On the Surface:**
```bash
sudo ip addr add 10.0.0.1/24 dev enp0s20f0u1
sudo ip link set enp0s20f0u1 up
```

**On the host PC:**
```bash
sudo ip addr add 10.0.0.2/24 dev enp0s1
sudo ip link set enp0s1 up
```

Use scripts: `sender_ethernet.py` + `receiver_ethernet.py`

Latency on direct Ethernet is typically **< 1ms**, essentially indistinguishable from a physical tablet.

#### Keeping internet on the host PC
If the host only has one Ethernet port, add a **USB → Ethernet adapter** for the direct link, keeping the built-in port for internet. Verify routing is correct:
```bash
ip route
```
Traffic to `10.0.0.x` should go through the USB adapter interface, everything else through the internet interface.

---

## 5. Running the scripts

Always start the **receiver first**, then the **sender**.

**On the host PC:**
```bash
# WiFi
sudo python receiver_wifi.py

# Ethernet
sudo python receiver_ethernet.py
```

**On the Surface:**
```bash
# WiFi
sudo python sender_wifi.py

# Ethernet
sudo python sender_ethernet.py
```

Press `Ctrl+C` on the sender to stop — the screen will restore automatically.

---

## 6. Turning off the Surface screen

The sender script handles this automatically via sysfs. If you need to do it manually:

```bash
# Off
brightnessctl set 0

# Restore
brightnessctl set 100%
```

---

## 7. Mapping the tablet to a specific monitor (host PC)

On **GNOME Wayland**, go to **Settings → Wacom Tablet** and select the desired monitor from the GUI.

Alternatively via gsettings (replace `DP-1` with your monitor name):
```bash
gsettings set org.gnome.desktop.peripherals.tablets:/org/gnome/desktop/peripherals/tablets/045e:0021:/ output "['DP-1', '', '']"
```

---

## 8. Reducing latency

In order of impact:

1. **Use direct Ethernet** instead of WiFi
2. **`TCP_NODELAY`** is already enabled in all scripts — disables Nagle's algorithm
3. **Increase process priority:**
   ```bash
   sudo nice -n -20 python sender_wifi.py
   sudo chrt -f 50 python sender_wifi.py  # real-time priority
   ```
4. **Measure your baseline:**
   ```bash
   ping -i 0.1 <host_ip>
   ```
   If ping < 1ms you're on a good connection and lag is elsewhere.

---

## 9. Troubleshooting

| Problem                                         | Cause                               | Solution                                                             |
| ----------------------------------------------- | ----------------------------------- | -------------------------------------------------------------------- |
| `/dev/ipts*` does not exist                     | `ithc` module not loaded            | `sudo modprobe ithc`                                                 |
| `iptsd.service` not found                       | Service is a template unit          | Use `systemctl start iptsd@0`                                        |
| `PermissionError` on `/dev/input/eventX`        | User not in `input` group           | `sudo usermod -aG input $USER` + `newgrp input`                      |
| `struct.error: 'I' format requires 0 <= number` | Tilt values can be negative         | Use `'i'` (signed) in struct format — already fixed in these scripts |
| evtest shows no events                          | Wayland compositor holds the device | Try from TTY (`Ctrl+Alt+F2`)                                         |
| Script crashes on keyboard detach               | IPTS device gets re-enumerated      | Already handled — script reconnects automatically                    |
| Pen not detected                                | IPTS driver not active              | `sudo dmesg \| grep -iE "ipts\|ithc"`                                |

---

## 10. Windows host

The receiver **does not work on Windows** — `evdev` and `uinput` are Linux-only.

---

## 11. Files

| File                   | Role                                                         | Machine |
| ---------------------- | ------------------------------------------------------------ | ------- |
| `sender_wifi.py`       | Reads pen events, streams over WiFi                          | Surface |
| `sender_ethernet.py`   | Reads pen events, streams over direct Ethernet               | Surface |
| `receiver_wifi.py`     | Creates virtual tablet device, receives over WiFi            | Host PC |
| `receiver_ethernet.py` | Creates virtual tablet device, receives over direct Ethernet | Host PC |
