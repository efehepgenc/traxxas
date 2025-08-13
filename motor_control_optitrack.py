import pygame
import serial
import time
import sys
import threading
import re
import ast # Python literal string'lerini güvenli bir şekilde değerlendirmek için

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
    """
    Gelen veriyi temizler, ayrıştırır ve ekrana yazdırır.
    Sadece geçerli karakterleri koruyarak ayrıştırma hatalarını önler.
    ast.literal_eval, string'i güvenli bir şekilde Python veri yapısına dönüştürür.
    """
    global last_print_ts

    # Gelen veriyi sadece geçerli karakterleri koruyarak temizle
    # Bu, 'ast.literal_eval'ın hata vermesini engellemeye yardımcı olur.
    cleaned_data = re.sub(r'[^0-9\.\,()\-\s]', '', line)

    try:
        # Temizlenmiş veriyi doğrudan Python literal olarak değerlendiriyoruz
        parsed_data = ast.literal_eval(cleaned_data.strip())
        
        # Gelen formatın bir tuple (rotasyon, konum, zaman) olduğunu varsayıyoruz
        if isinstance(parsed_data, tuple) and len(parsed_data) == 3:
            rotation_tuple = parsed_data[0]
            position_tuple = parsed_data[1]
            current_time = parsed_data[2]
            
            # Gelen verinin doğru formatta olduğunu doğrula ve ekrana yazdır
            if isinstance(rotation_tuple, tuple) and isinstance(position_tuple, tuple) and isinstance(current_time, (int, float)):
                now = time.time()
                if now - last_print_ts >= (1.0 / PRINT_MAX_HZ):
                    print(f"[OptiTrack] Pos: {list(position_tuple)} | Rot: {list(rotation_tuple)} | Time: {current_time:.3f}")
                    last_print_ts = now
            else:
                # Format beklenildiği gibi değilse uyarı ver
                print(f"[!] Hata: Beklenmedik veri formatı. Temizlenmiş veri: '{cleaned_data}'")
        
    except (ValueError, SyntaxError, IndexError) as e:
        # Ayrıştırma hatası oluşursa, hem orijinal hem de temizlenmiş veriyi göster
        print(f"[!] Veri ayrıştırma hatası: {e} | Orijinal Data: '{line}' | Temizlenmiş Data: '{cleaned_data}'")


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
                bt_buffer += text
                
            if '\n' in bt_buffer:
                lines = bt_buffer.split('\n')
                bt_buffer = lines[-1]
                for raw in lines[:-1]:
                    s = raw.strip()
                    if not s:
                        continue
                    process_and_print_position_data(s)
        except serial.SerialException:
            bt_buffer = ''
            try:
                bt_serial.reset_input_buffer()
            except Exception:
                pass
        except Exception:
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
    print("Başlatıldı: Motor kontrol (thread) + OptiTrack okuma (thread)")

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


