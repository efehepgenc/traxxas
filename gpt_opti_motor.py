import pygame
import serial
import time
import sys
import threading

# --- AYARLAR ---
ARDUINO_PORT = '/dev/ttyACM0'
ARDUINO_BAUD = 9600
BT_PORT = '/dev/serial0'
BT_BAUD = 38400
LOOP_DELAY = 0.05
JOYSTICK_ID = 0

# --- GLOBALLER ---
arduino = None
ser_bt = None
last_throttle = 1500
last_steering = 'c'

# --- Arduino bağlantısı ---
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

# --- Bluetooth bağlantısı ---
def setup_bluetooth():
    global ser_bt
    try:
        ser_bt = serial.Serial(BT_PORT, BT_BAUD, timeout=0.1)
        time.sleep(2)
        ser_bt.reset_input_buffer()
        print(f"[✓] Bluetooth bağlantısı sağlandı: {BT_PORT}")
    except serial.SerialException as e:
        print(f"[X] Bluetooth bağlantı hatası: {e}")
        sys.exit(1)

# --- Bluetooth verisi ayrıştırıcı ---
def process_and_print_position_data(data):
    try:
        cleaned_data = data.strip('[]\n\r ')
        parts = cleaned_data.rsplit(',', 1)
        if len(parts) == 2:
            time_data = float(parts[1].strip())
            coords_data = parts[0].strip()
            coords_parts = coords_data.split('),(')
            if len(coords_parts) == 2:
                rotation_data = coords_parts[0].strip('(')
                position_data = coords_parts[1].strip(')')
                rot_coords = [float(c.strip()) for c in rotation_data.split(',')]
                pos_coords = [float(c.strip()) for c in position_data.split(',')]
                if len(rot_coords) == 3 and len(pos_coords) == 3:
                    print(f"[Konum] Pos: {pos_coords} | Rot: {rot_coords} | Zaman: {time_data:.3f}")
    except Exception as e:
        print(f"[!] Ayrıştırma hatası: {e} → Veri: {data}")

# --- Bluetooth dinleme iş parçacığı ---
def bluetooth_listener():
    received_buffer = ""
    while True:
        if ser_bt.in_waiting > 0:
            received_bytes = ser_bt.read(ser_bt.in_waiting)
            received_buffer += received_bytes.decode('utf-8', errors='ignore')
            while '\n' in received_buffer:
                line, received_buffer = received_buffer.split('\n', 1)
                if line.strip():
                    process_and_print_position_data(line.strip())
        time.sleep(0.01)

# --- Arduino’ya komut gönder ---
def send_command(command):
    if arduino and arduino.is_open:
        try:
            arduino.write((command + "\n").encode('utf-8'))
        except serial.SerialException as e:
            print(f"[X] Seri yazma hatası: {e}")

# --- Joystick ile kontrol döngüsü ---
def control_loop():
    global last_throttle, last_steering

    try:
        pygame.init()
        pygame.joystick.init()
        joystick = pygame.joystick.Joystick(JOYSTICK_ID)
        joystick.init()
        print(f"[✓] Kontrolcü: {joystick.get_name()}")
    except pygame.error as e:
        print(f"[X] Kontrolcü bulunamadı: {e}")
        sys.exit(1)

    while True:
        pygame.event.pump()

        forward_axis = (joystick.get_axis(2) + 1) / 2
        reverse_axis = (joystick.get_axis(5) + 1) / 2
        current_throttle = 1500

        if reverse_axis > 0.05 and reverse_axis > forward_axis:
            current_throttle = int(1500 - reverse_axis * 500)
        elif forward_axis > 0.05:
            current_throttle = int(1500 + forward_axis * 500)

        steer_axis = joystick.get_axis(3)
        current_steering = 'c'
        if steer_axis > 0.3:
            current_steering = 'r'
        elif steer_axis < -0.3:
            current_steering = 'l'

        if abs(current_throttle - last_throttle) > 5:
            send_command(f"t{current_throttle}")
            last_throttle = current_throttle

        if current_steering != last_steering:
            send_command(f"s{current_steering}")
            last_steering = current_steering

        time.sleep(LOOP_DELAY)

# === MAIN ===
if __name__ == "__main__":
    setup_arduino()
    setup_bluetooth()

    threading.Thread(target=bluetooth_listener, daemon=True).start()
    control_loop()
