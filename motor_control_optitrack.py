import pygame
import serial
import time
import sys
import re  # Veri temizleme için
import ast # Python literal string'lerini güvenli bir şekilde değerlendirmek için

# --- AYARLAR ---
ARDUINO_PORT = '/dev/ttyACM0'
ARDUINO_BAUD = 9600
BT_PORT = '/dev/serial0'
BT_BAUD = 38400
LOOP_DELAY = 0.02  # Ana döngü gecikmesi (daha hızlı)
JOYSTICK_ID = 0

# --- Global değişkenler ---
arduino = None
bt_serial = None
last_throttle = 1500
last_steering = 'c'
# Gelen veriyi satır satır işlemek için tampon
bt_buffer = ""

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

# --- Veri Temizleme ve Ayrıştırma ---
def process_and_print_position_data(data):
    """
    Gelen veriyi temizler, ayrıştırır ve ekrana yazdırır.
    Sadece geçerli karakterleri koruyarak ayrıştırma hatalarını önler.
    """
    global bt_buffer
    
    # Sadece sayılar, virgül, eksi, nokta, parantez ve boşluk karakterlerini koruyan bir regex.
    # Bu, gelen bozuk karakterleri etkili bir şekilde temizler.
    cleaned_data = re.sub(r'[^-0-9\.,\(\)\[\]\s]', '', data)
    
    # Temizlenmiş veriyi doğrudan ast.literal_eval ile ayrıştırmaya çalış
    try:
        # ast.literal_eval, string'i güvenli bir şekilde Python veri yapısına dönüştürür.
        # Bu yaklaşım, karmaşık veri formatlarını doğru bir şekilde işler.
        parsed_data = ast.literal_eval(cleaned_data.strip())
        
        # Gelen formatın bir tuple (rotasyon, konum, zaman) olduğunu varsayıyoruz
        if isinstance(parsed_data, tuple) and len(parsed_data) == 3:
            rotation_tuple = parsed_data[0]
            position_tuple = parsed_data[1]
            current_time = parsed_data[2]
            
            # Gelen verinin doğru formatta olduğunu doğrula ve yazdır
            if isinstance(rotation_tuple, tuple) and isinstance(position_tuple, tuple) and isinstance(current_time, (int, float)):
                print(f"[OptiTrack] Pos: {position_tuple} | Rot: {rotation_tuple} | Time: {current_time:.3f}")
            else:
                # Format beklenildiği gibi değilse uyarı ver
                print(f"[!] Hata: Beklenmedik veri formatı. Temizlenmiş veri: '{cleaned_data}'")

    except (ValueError, SyntaxError, IndexError) as e:
        # Ayrıştırma hatası oluşursa, hem orijinal hem de temizlenmiş veriyi göster
        print(f"[!] Veri ayrıştırma hatası: {e} | Orijinal Data: '{data}' | Temizlenmiş Data: '{cleaned_data}'")


# --- Bluetooth Veri Oku ---
def read_bluetooth_data():
    """
    Bluetooth'tan gelen veriyi okur ve tamponlar.
    Tamamlanmış satırları (newline karakteri ile biten) işler.
    """
    global bt_serial, bt_buffer
    if not bt_serial or not bt_serial.is_open:
        return
    
    try:
        if bt_serial.in_waiting > 0:
            received_bytes = bt_serial.read(bt_serial.in_waiting)
            bt_buffer += received_bytes.decode('utf-8', errors='ignore')
            
            # Tamamlanmış bir satır varsa işleme al
            while '\n' in bt_buffer:
                line, bt_buffer = bt_buffer.split('\n', 1)
                line = line.strip()
                if line:
                    process_and_print_position_data(line)
                    
    except serial.SerialException:
        bt_serial.reset_input_buffer()
        print("[!] Seri port okuma hatası, tampon sıfırlandı.")
    except Exception as e:
        print(f"[!] Genel hata oluştu: {e}")

# --- Komut Gönder ---
def send_command(cmd):
    if arduino and arduino.is_open:
        try:
            arduino.write((cmd + '\n').encode('utf-8'))
        except serial.SerialException:
            pass

# --- Ana Döngü (Joystick + Bluetooth) ---
def main_loop():
    global last_throttle, last_steering
    try:
        pygame.init()
        pygame.joystick.init()
        if pygame.joystick.get_count() == 0:
            raise pygame.error("No joystick found")
        js = pygame.joystick.Joystick(JOYSTICK_ID)
        js.init()
        print(f"[✓] Kontrolcü: {js.get_name()}")
    except pygame.error as e:
        print(f"[X] Kontrolcü bulunamadı: {e}")
        sys.exit(1)

    while True:
        pygame.event.pump()
        
        # Throttle hesapla (F710 eksen haritası)
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
            
        # Steering hesapla (F710 eksen haritası)
        sv = js.get_axis(3)
        steer_cmd = 'c'
        if sv > 0.3:
            steer_cmd = 'r'
        elif sv < -0.3:
            steer_cmd = 'l'
            
        if steer_cmd != last_steering:
            send_command(f"s{steer_cmd}")
            last_steering = steer_cmd
            
        # Bluetooth verisini oku ve işle
        read_bluetooth_data()
        
        time.sleep(LOOP_DELAY)

# === Program Başlangıcı ===
if __name__ == '__main__':
    setup_arduino()
    setup_bluetooth()
    print("Başlatıldı: Motor kontrol ve OptiTrack veri okuma aynı döngüde.")
    try:
        main_loop()
    except KeyboardInterrupt:
        print("\n[!] Program durduruldu. Bağlantılar kapatılıyor...")
    finally:
        send_command("t1500")
        send_command("sc")
        if arduino and arduino.is_open:
            arduino.close()
        if bt_serial and bt_serial.is_open:
            bt_serial.close()
        pygame.quit()
        print("[✓] Program güvenli bir şekilde sonlandırıldı.")
        sys.exit(0)

