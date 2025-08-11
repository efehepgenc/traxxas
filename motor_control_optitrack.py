import pygame
import serial
import time
import sys
import threading
import re

# --- AYARLAR ---
ARDUINO_PORT = '/dev/ttyACM0'
ARDUINO_BAUD = 9600
BT_PORT = '/dev/serial0'
BT_BAUD = 38400
JOY_LOOP_HZ = 50            # 50 Hz kontrol döngüsü
BT_READ_SLEEP = 0.005       # BT thread kısa bekleme
PRINT_MAX_HZ = 10           # En fazla 10 Hz veri yazdır
JOYSTICK_ID = 0

# --- Global değişkenler ---
arduino = None
bt_serial = None
last_throttle = 1500
last_steering = 'c'

# BT okuma için kalıcı tampon ve yazdırma sınırlayıcı
bt_buffer = ''
last_print_ts = 0.0

# OptiTrack satırı (rot, pos, time) regex (float'ları yakalar)
pattern = re.compile(r'^\(\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*\)\s*,\s*\(\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*\)\s*,\s*([-+]?\d*\.?\d+)\s*$')

# --- Arduino Bağlantısı ---
def setup_arduino():
    global arduino
    try:
        arduino = serial.Serial(ARDUINO_PORT, ARDUINO_BAUD, timeout=0)
        time.sleep(2)
        arduino.reset_input_buffer()
        print(f"[✓] Arduino bağlandı: {ARDUINO_PORT}")
    except serial.SerialException as e:
        print(f"[X] Arduino bağlantı hatası: {e}")
        sys.exit(1)

# --- Bluetooth Bağlantısı (OptiTrack Verisi) ---
def setup_bluetooth():
    global bt_serial
    try:
        bt_serial = serial.Serial(BT_PORT, BT_BAUD, timeout=0)
        time.sleep(2)
        bt_serial.reset_input_buffer()
        print(f"[✓] Bluetooth bağlantısı: {BT_PORT}")
    except serial.SerialException as e:
        print(f"[X] Bluetooth bağlantı hatası: {e}")
        sys.exit(1)

# --- OptiTrack verisini işle ---
def process_and_print_position_data(line: str):
    global last_print_ts
    m = pattern.match(line)
    if not m:
        return  # bozuk satırı atla
    rot = list(map(float, m.group(1, 2, 3)))
    pos = list(map(float, m.group(4, 5, 6)))
    t = float(m.group(7))

    now = time.time()
    if now - last_print_ts >= (1.0 / PRINT_MAX_HZ):
        print(f"[OptiTrack] Pos: {pos} | Rot: {rot} | Time: {t:.3f}")
        last_print_ts = now

# --- Bluetooth okuma thread'i ---
def bluetooth_reader():
    global bt_buffer
    while True:
        try:
            if bt_serial is None:
                time.sleep(BT_READ_SLEEP)
                continue
            available = bt_serial.in_waiting
            if available:
                chunk = bt_serial.read(available)
                text = chunk.decode('utf-8', errors='ignore')
                # Yalnızca izinli karakterleri tut (parazit önleme)
                text = re.sub(r'[^0-9\n\r\t\.\,()\-\+\s]', '', text)
                bt_buffer += text

            # Satır bazlı ayırma (tamamlanmamış son parça bt_buffer'da kalır)
            if '\n' in bt_buffer:
                lines = bt_buffer.split('\n')
                bt_buffer = lines[-1]
                for raw in lines[:-1]:
                    s = raw.strip()
                    if not s:
                        continue
                    process_and_print_position_data(s)
        except serial.SerialException:
            # Geçici hata → tamponu temizle ve devam et
            bt_buffer = ''
            try:
                bt_serial.reset_input_buffer()
            except Exception:
                pass
        except Exception:
            # Diğer hatalar sessiz geçilsin (veri akışını kesmeyelim)
            pass
        time.sleep(BT_READ_SLEEP)

# --- Arduino'ya komut gönder ---
def send_command(cmd: str):
    if arduino and arduino.is_open:
        try:
            arduino.write((cmd + '\n').encode('utf-8'))
        except serial.SerialException:
            pass

# --- Joystick kontrol thread'i ---
def joystick_control():
    global last_throttle, last_steering
    try:
        pygame.init()
        pygame.joystick.init()
        js = pygame.joystick.Joystick(JOYSTICK_ID)
        js.init()
        print(f"[✓] Kontrolcü: {js.get_name()}")
    except pygame.error:
        print("[X] Kontrolcü bulunamadı")
        sys.exit(1)

    period = 1.0 / JOY_LOOP_HZ
    next_ts = time.time()

    while True:
        start = time.time()
        pygame.event.pump()

        # Throttle
        fw = (js.get_axis(2) + 1) / 2
        rv = (js.get_axis(5) + 1) / 2
        throttle = 1500
        if rv > 0.05 and rv > fw:
            throttle = int(1500 - rv * 500)
        elif fw > 0.05:
            throttle = int(1500 + fw * 500)
        if abs(throttle - last_throttle) > 5:
            send_command(f"t{throttle}")
            last_throttle = throttle

        # Steering
        sv = js.get_axis(3)
        steer_cmd = 'c'
        if sv > 0.3:
            steer_cmd = 'r'
        elif sv < -0.3:
            steer_cmd = 'l'
        if steer_cmd != last_steering:
            send_command(f"s{steer_cmd}")
            last_steering = steer_cmd

        # Sabit frekanslı döngü (joystick)
        next_ts += period
        sleep_for = next_ts - time.time()
        if sleep_for > 0:
            time.sleep(sleep_for)
        else:
            # Fazla geciktiysek bir sonraki adıma geç
            next_ts = time.time()

# === Program Başlangıcı ===
if __name__ == '__main__':
    setup_arduino()
    setup_bluetooth()
    print("Basladi: Motor kontrol (thread) + OptiTrack okuma (thread)")

    t_bt = threading.Thread(target=bluetooth_reader, daemon=True)
    t_js = threading.Thread(target=joystick_control, daemon=True)
    t_bt.start()
    t_js.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nKapatiliyor...")
        send_command("t1500")
        send_command("sc")
        try:
            if arduino and arduino.is_open:
                arduino.close()
            if bt_serial and bt_serial.is_open:
                bt_serial.close()
        except Exception:
            pass
        pygame.quit()
        print("Gule gule!")
        sys.exit(0)


