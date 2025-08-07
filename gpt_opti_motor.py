import pygame
import serial
import time
import sys
import threading
import re  # For filtering non-printable characters

# --- AYARLAR ---
ARDUINO_PORT = '/dev/ttyACM0'
ARDUINO_BAUD = 9600
BT_PORT = '/dev/serial0'
BT_BAUD = 38400
LOOP_DELAY = 0.05
JOYSTICK_ID = 0

# --- Global değişkenler ---
arduino = None
bt_serial = None
last_throttle = 1500
last_steering = 'c'

# --- Arduino Bağlantısı ---
def setup_arduino():
    global arduino
    try:
        arduino = serial.Serial(ARDUINO_PORT, ARDUINO_BAUD, timeout=1)
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
        bt_serial = serial.Serial(BT_PORT, BT_BAUD, timeout=0.1)
        time.sleep(2)
        bt_serial.reset_input_buffer()
        print(f"[✓] Bluetooth bağlantısı: {BT_PORT}")
    except serial.SerialException as e:
        print(f"[X] Bluetooth bağlantı hatası: {e}")
        sys.exit(1)

# --- Gelen Veriyi Ayrıştır ve Yazdır ---
def process_and_print_position_data(data):
    try:
        cleaned = data.strip('[]\n\r ')
        parts = cleaned.rsplit(',', 1)
        if len(parts) != 2:
            return
        time_data = float(parts[1].strip())
        coords = parts[0].strip()
        if '),(' not in coords:
            return
        rot_part, pos_part = coords.split('),(')
        rot_vals = [float(x) for x in rot_part.strip('(').split(',')]
        pos_vals = [float(x) for x in pos_part.strip(')').split(',')]
        if len(rot_vals) == 3 and len(pos_vals) == 3:
            print(f"[OptiTrack] Pos: {pos_vals} | Rot: {rot_vals} | Time: {time_data:.3f}")
    except Exception as e:
        print(f"[!] Veri ayrıştırma hatası: {e} | Data: {data}")

# --- Bluetooth Dinleme Thread'i ---
def bluetooth_listener():
    buffer = ""
    while True:
        if bt_serial and bt_serial.in_waiting > 0:
            data = bt_serial.read(bt_serial.in_waiting)
            text = data.decode('utf-8', errors='ignore')
            buffer += text
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                raw = line.strip()
                filtered = re.sub(r'[^0-9\.\,()\-\s]', '', raw)
                if '(' in filtered and ')' in filtered and ',' in filtered:
                    process_and_print_position_data(filtered)
        time.sleep(0.01)

# --- Komut Gönder ---
def send_command(cmd):
    if arduino and arduino.is_open:
        try:
            arduino.write((cmd + '\n').encode('utf-8'))
        except serial.SerialException as e:
            print(f"[X] Serial write error: {e}")

# --- Manuel Sürüş Döngüsü ---
def control_loop():
    global last_throttle, last_steering
    try:
        pygame.init()
        pygame.joystick.init()
        js = pygame.joystick.Joystick(JOYSTICK_ID)
        js.init()
        print(f"[✓] Kontrolcü: {js.get_name()}")
    except pygame.error as e:
        print(f"[X] Kontrolcü bulunamadı: {e}")
        sys.exit(1)

    while True:
        pygame.event.pump()
        fw = (js.get_axis(2) + 1) / 2
        re = (js.get_axis(5) + 1) / 2
        throttle = 1500
        if re > 0.05 and re > fw:
            throttle = int(1500 - re * 500)
        elif fw > 0.05:
            throttle = int(1500 + fw * 500)
        if abs(throttle - last_throttle) > 5:
            send_command(f"t{throttle}")
            last_throttle = throttle
        steer = js.get_axis(3)
        steering_cmd = 'c'
        if steer > 0.3:
            steering_cmd = 'r'
        elif steer < -0.3:
            steering_cmd = 'l'
        if steering_cmd != last_steering:
            send_command(f"s{steering_cmd}")
            last_steering = steering_cmd
        time.sleep(LOOP_DELAY)

# === Program Başlangıcı ===
if __name__ == '__main__':
    setup_arduino()
    setup_bluetooth()
    # İki eylemi paralel başlat
    t1 = threading.Thread(target=bluetooth_listener, daemon=True)
    t2 = threading.Thread(target=control_loop, daemon=True)
    t1.start()
    t2.start()
    # Ana thread uykuya geçsin
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nProgram sonlandırılıyor...")
        send_command("t1500")
        send_command("sc")
        if arduino and arduino.is_open:
            arduino.close()
        if bt_serial and bt_serial.is_open:
            bt_serial.close()
        pygame.quit()
        print("Bağlantılar kapatıldı. Güle güle!")
        sys.exit(0)
