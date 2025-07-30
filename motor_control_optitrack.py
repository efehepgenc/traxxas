import serial
import time
import sys
import math
import bluetooth # HC-05 iletişimi için

# --- AYARLAR ---
# Bluetooth HC-05 Haberleşme (Konum Verisi Alan)
# Konum Arduino'suna bağlı HC-05'in MAC adresi
HC05_POS_MAC_ADDRESS = 'XX:XX:XX:XX:XX:XX' # BURAYI KENDİ KONUM HC-05 MAC ADRESİNİZLE DEĞİŞTİRİN!
HC05_POS_PORT = 1

# Rover Arduino Seri Haberleşme (USB ile Bağlı)
ARDUINO_SERIAL_PORT = '/dev/ttyACM0' # Rover Arduino'nuzun bağlı olduğu USB portu
ARDUINO_BAUD_RATE = 9600             # Rover Arduino kodunuzdaki ile aynı olmalı

# Rover Kontrol Parametreleri
THROTTLE_MID = 1500 # ESC için nötr değeri
THROTTLE_FORWARD_SPEED = 1550 # İleri giderken kullanılacak sabit hız
THROTTLE_STOP_THRESHOLD = 5 # Durma komutu gönderildiğinde küçük salınımları engellemek için

# Navigasyon Parametreleri
current_rover_x = 0.0
current_rover_y = 0.0
current_rover_z = 0.0 # Z koordinatı OptiTrack'ten gelebilir
current_rover_heading = 0.0 # Rover'ın anlık yönü (derece cinsinden, 0-360)

target_x = 0.0
target_y = 0.0
target_z = 0.0
is_target_set = False # Yeni bir hedef belirlenip belirlenmediğini takip et

TARGET_REACH_DISTANCE = 0.5 # Hedefe ne kadar yaklaştığımızda duracağımız (birimlerinizle aynı olmalı)
STEER_THRESHOLD_DEGREES = 0.5 # Hedefe dönmek için açısal eşik (bu eşikten büyükse dön)

# Döngü Zamanlaması
LOOP_DELAY_SEC = 0.05 # Saniyede 20 (1/0.05) güncelleme. CPU kullanımını düşürür.

# Haberleşme Nesneleri
hc05_pos_socket = None # Konum verisi için Bluetooth soketi
rover_arduino_serial = None # Rover kontrolü için seri port nesnesi

def setup_hc05_pos_receiver():
    global hc05_pos_socket
    print(f"Konum Alıcı HC-05'e ({HC05_POS_MAC_ADDRESS}) bağlanmaya çalışılıyor...")
    try:
        hc05_pos_socket = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        hc05_pos_socket.connect((HC05_POS_MAC_ADDRESS, HC05_POS_PORT))
        hc05_pos_socket.settimeout(0.1) # Non-blocking read
        print(f"Konum Alıcı HC-05'e başarıyla bağlanıldı.")
        return True
    except bluetooth.btcommon.BluetoothError as e:
        print(f"HATA: Konum Alıcı HC-05'e bağlanılamadı: {e}. Lütfen MAC adresini, eşleşmeyi ve Bluetooth servisini kontrol edin.")
        return False

def setup_rover_arduino_serial():
    global rover_arduino_serial
    try:
        rover_arduino_serial = serial.Serial(ARDUINO_SERIAL_PORT, ARDUINO_BAUD_RATE, timeout=0.1)
        time.sleep(2) # Arduino'nun kendine gelmesi için zaman tanı
        rover_arduino_serial.reset_input_buffer()
        print(f"Rover Arduino'ya {ARDUINO_SERIAL_PORT} portundan başarıyla bağlanıldı.")
        return True
    except serial.SerialException as e:
        print(f"HATA: Rover Arduino'ya bağlanılamadı: {e}")
        return False

# --- Rover'a Komut Gönderme Fonksiyonu (Seri Port üzerinden) ---
def send_command_to_rover(command_str):
    """Rover Arduino'ya seri port üzerinden komutları güvenli bir şekilde gönderir."""
    if rover_arduino_serial and rover_arduino_serial.is_open:
        try:
            full_command = command_str + "\n" # Arduino'nun satır sonu beklediği için '\n' ekle
            rover_arduino_serial.write(full_command.encode('ascii')) # Komutları ASCII olarak gönder
            # print(f"Rover'a gönderildi (USB): {full_command.strip()}") # Hata ayıklama için
            return True
        except serial.SerialException as e:
            print(f"UYARI: Seri yazma hatası (Rover), bağlantı kesilmiş olabilir: {e}")
            return False
        except Exception as e:
            print(f"UYARI: Seri yazma sırasında beklenmeyen bir hata oluştu (Rover): {e}")
            return False
    else:
        print("UYARI: Komut göndermeye çalışıldı ancak Rover Arduino seri portu açık değil.")
        return False

# --- Konum Verisi İşleme Fonksiyonu ---
def process_position_data(data):
    """Bluetooth'tan gelen konum verisini ayrıştırır ve global değişkenleri günceller."""
    global current_rover_x, current_rover_y, current_rover_z, current_rover_heading

    if data.startswith("POS"):
        try:
            # 'POSX10.5Y20.2Z5.0H45.0' formatı bekleniyor
            parts = {}
            remaining = data[3:] # 'POS' kısmını atla
            
            x_idx = remaining.find('X')
            y_idx = remaining.find('Y')
            z_idx = remaining.find('Z')
            h_idx = remaining.find('H')

            if x_idx != -1 and y_idx != -1 and z_idx != -1 and h_idx != -1:
                current_rover_x = float(remaining[x_idx+1 : y_idx])
                current_rover_y = float(remaining[y_idx+1 : z_idx])
                current_rover_z = float(remaining[z_idx+1 : h_idx])
                current_rover_heading = float(remaining[h_idx+1 :])

                # Yönü 0-360 arasına normalleştir
                current_rover_heading = current_rover_heading % 360
                if current_rover_heading < 0:
                    current_rover_heading += 360

                # print(f"Rover'ın güncel konumu alındı: X={current_rover_x:.2f}, Y={current_rover_y:.2f}, Z={current_rover_z:.2f}, Yön={current_rover_heading:.2f}°")
            else:
                print(f"HATA: Konum verisi ayrıştırma hatası. Geçersiz format: {data}")
                print("Beklenen format: POSX<sayı>Y<sayı>Z<sayı>H<sayı>")

        except (IndexError, ValueError) as e:
            print(f"HATA: Konum verisi ayrıştırma hatası. Geçersiz format: {data}. Hata: {e}")
            print("Beklenen format: POSX<sayı>Y<sayı>Z<sayı>H<sayı>")
    else:
        print(f"UYARI: Bilinmeyen Bluetooth verisi veya formatı: {data}")

# --- Ana Navigasyon Döngüsü ---
def navigate_rover():
    global target_x, target_y, is_target_set
    global current_rover_x, current_rover_y, current_rover_heading

    if not is_target_set:
        return # Hedef belirlenmediyse navigasyon yapma

    dx = target_x - current_rover_x
    dy = target_y - current_rover_y
    distance_to_target = math.hypot(dx, dy)

    if distance_to_target < TARGET_REACH_DISTANCE:
        send_command_to_rover(f"t{THROTTLE_MID}") # Motoru nötr
        send_command_to_rover("sc") # Direksiyonu merkez
        print(f"Hedefe ulaşıldı! Son konum: ({current_rover_x:.2f}, {current_rover_y:.2f})")
        is_target_set = False
        return

    # Hedefe olan açıyı hesapla (radyan cinsinden, sonra dereceye çevir)
    angle_to_target_rad = math.atan2(dy, dx)
    angle_to_target_deg = math.degrees(angle_to_target_rad)

    # Rover'ın mevcut yönü ile hedefe olan açı arasındaki farkı bul
    angle_diff = angle_to_target_deg - current_rover_heading
    if angle_diff > 180:
        angle_diff -= 360
    elif angle_diff < -180:
        angle_diff += 360

    print(f"Konum: ({current_rover_x:.2f}, {current_rover_y:.2f}), Yön: {current_rover_heading:.2f}°, Hedef: ({target_x}, {target_y}), Mesafe: {distance_to_target:.2f}, Açı Farkı: {angle_diff:.2f}°")

    if abs(angle_diff) > STEER_THRESHOLD_DEGREES:
        if angle_diff > 0: # Sağa dön (hedef sağda)
            send_command_to_rover("sr")
        else: # Sola dön (hedef solda)
            send_command_to_rover("sl")
        send_command_to_rover(f"t{THROTTLE_MID}") # Dönüş sırasında ilerlemeyi durdur
    else: # Yön hedefe yakınsa ileri git
        send_command_to_rover(f"t{THROTTLE_FORWARD_SPEED}")
        send_command_to_rover("sc") # Düz gitmek için direksiyonu ortaya al

# --- Ana Program Akışı ---
if __name__ == "__main__":
    try:
        import pygame
        pygame.init()
    except Exception as e:
        print(f"UYARI: Pygame başlatılamadı: {e}. Program sonlandırılırken kontrol için 'Ctrl+C' kullanın.")

    # Bluetooth (konum) ve Seri (rover) bağlantılarını kur
    if not setup_hc05_pos_receiver():
        sys.exit(1)
    if not setup_rover_arduino_serial():
        sys.exit(1)

    print("\nKonum Arduino'sundan veri bekleniyor ve Rover'a komut gönderilmeye başlanacak.")
    print(f"Başlangıç Konumu: ({current_rover_x:.2f}, {current_rover_y:.2f}), Yön: {current_rover_heading:.2f}°")
    print("Çıkmak için CTRL+C'ye basın.")

    # --- TEST AMAÇLI: Bir hedef belirleyelim ---
    target_x = 100.0 # Örnek hedef X koordinatı
    target_y = 50.0  # Örnek hedef Y koordinatı
    is_target_set = True
    print(f"TEST HEDEFİ BELİRLENDİ: X={target_x}, Y={target_y}")

    try:
        while True:
            # Konum Arduino'sundan veri oku (Bluetooth üzerinden)
            try:
                pos_data = hc05_pos_socket.recv(1024).decode('utf-8').strip()
                if pos_data:
                    process_position_data(pos_data) # Gelen konumu işle
            except bluetooth.btcommon.BluetoothError as e:
                if "timed out" not in str(e):
                    print(f"Konum Alıcı Bluetooth okuma hatası: {e}")
            except Exception as e:
                print(f"Konum verisi alırken beklenmeyen bir hata oluştu: {e}")

            # Navigasyon mantığını çalıştır
            navigate_rover()

            pygame.event.pump()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    print("Pygame kapatma olayı algılandı. Çıkış yapılıyor.")
                    raise KeyboardInterrupt

            time.sleep(LOOP_DELAY_SEC)

    except KeyboardInterrupt:
        print("\nProgram sonlandırılıyor. Araç durduruluyor.")
    finally:
        # --- Temizlik ---
        print("Temizlik yapılıyor...")
        send_command_to_rover(f"t{THROTTLE_MID}") # Motoru nötr
        send_command_to_rover("sc")              # Direksiyonu ortaya al
        time.sleep(0.1)

        if hc05_pos_socket:
            hc05_pos_socket.close()
            print("Konum Alıcı HC-05 soketi kapatıldı.")
        if rover_arduino_serial and rover_arduino_serial.is_open:
            rover_arduino_serial.close()
            print("Rover Arduino seri portu kapatıldı.")
        
        if 'pygame' in sys.modules and pygame.get_init():
             pygame.quit()
        print("Tüm bağlantılar kapatıldı. Güle güle!")
        sys.exit(0)
