import pygame
import serial
import time
import sys
import re

# --- AYARLAR ---
ARDUINO_PORT = '/dev/ttyACM0'
ARDUINO_BAUD = 9600
BT_PORT = '/dev/serial0'
BT_BAUD = 38400
LOOP_DELAY = 0.02  # Döngü gecikmesi
JOYSTICK_ID = 0

# --- Seri bağlantılar ---
arduino = None
bt_serial = None

# --- Son durumlar ---
last_throttle = 1500
last_steering = 'c'
bt_buffer = ''  # Gelen bluetooth verisi tamponu

# --- Regex kalıbı ---
# (rotX,rotY,rotZ),(posX,posY,posZ),time
pattern = re.compile(r'''^\(\s*([-+]?\d*\.\d+),\s*([-+]?\d*\.\d+),\s*([-+]?\d*\.\d+)\)\s*,\s*\(\s*([-+]?\d*\.\d+),\s*([-+]?\d*\.\d+),\s*([-+]?\d*\.\d+)\)\s*,\s*([-+]?\d*\.\d+)$''')

# --- Arduino bağlantısı ---
def setup_arduino():
    global arduino
    try:
        arduino = serial.Serial(ARDUINO_PORT, ARDUINO_BAUD, timeout=1)
        time.sleep(2)
        arduino.reset_input_buffer()
        print(f"[✓] Arduino: {ARDUINO_PORT}")
    except Exception as e:
        print(f"[X] Arduino bağlantı hatası: {e}")
        sys.exit(1)

# --- Bluetooth bağlantısı ---
def setup_bluetooth():
    global bt_serial
    try:
        bt_serial = serial.Serial(BT_PORT, BT_BAUD, timeout=0.1)
        time.sleep(2)
        bt_serial.reset_input_buffer()
        print(f"[✓] Bluetooth: {BT_PORT}")
    except Exception as e:
        print(f"[X] Bluetooth bağlantı hatası: {e}")
        sys.exit(1)

# --- Bluetooth verisi okuma ve işleme ---
def read_bluetooth_data():
    global bt_buffer
    try:
        if bt_serial.in_waiting > 0:
            data = bt_serial.read(bt_serial.in_waiting)
            text = data.decode('utf-8', errors='ignore')
            bt_buffer += text
        # Tamamlanmış satırları işle
        lines = bt_buffer.split('\n')
        bt_buffer = lines[-1]  # Son parça, eksik veri
        for line in lines[:-1]:
            raw = line.strip()
            if not raw:
                continue
            m = pattern.match(raw)
            if m:
                rot = list(map(float, m.group(1,2,3)))
                pos = list(map(float, m.group(4,5,6)))
                t   = float(m.group(7))
                print(f"[OptiTrack] Pos: {pos} | Rot: {rot} | Time: {t:.3f}")
            # Hatalı satırları yoksay
    except Exception:
        # Bulanık veri durumunda tamponu temizle
        bt_buffer = ''

# --- Arduino'ya komut gönderme ---
def send_command(cmd):
    if arduino and arduino.is_open:
        try:
            arduino.write((cmd + '\n').encode())
        except:
            pass

# --- Ana döngü: joystick + bluetooth ---
def main_loop():
    global last_throttle, last_steering
    # Joystick başlat
    try:
        pygame.init()
        pygame.joystick.init()
        js = pygame.joystick.Joystick(JOYSTICK_ID)
        js.init()
        print(f"[✓] Kontrolcü: {js.get_name()}")
    except:
        print("[X] Kontrolcü bulunamadı")
        sys.exit(1)
    # Döngü
    while True:
        pygame.event.pump()
        # Throttle hesabi
        fw = (js.get_axis(2) + 1) / 2
        rv = (js.get_axis(5) + 1) / 2
        thr = 1500
        if rv > 0.05 and rv > fw:
            thr = int(1500 - rv * 500)
        elif fw > 0.05:
            thr = int(1500 + fw * 500)
        if abs(thr - last_throttle) > 5:
            send_command(f"t{thr}")
            last_throttle = thr
        # Steering hesabi
        sv = js.get_axis(3)
        cmd = 'c'
        if sv > 0.3:
            cmd = 'r'
        elif sv < -0.3:
            cmd = 'l'
        if cmd != last_steering:
            send_command(f"s{cmd}")
            last_steering = cmd
        # Bluetooth oku
        read_bluetooth_data()
        time.sleep(LOOP_DELAY)

# --- Program Start ---
if __name__ == '__main__':
    setup_arduino()
    setup_bluetooth()
    print("Başlatıldı: hem sürüş hem veri okuma tek döngüde.")
    main_loop()
