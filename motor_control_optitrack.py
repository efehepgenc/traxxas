import pygame
import serial
import time
import sys
import ast # Python literal string'lerini güvenli bir şekilde değerlendirmek için

# --- GENEL AYARLAR ---
JOYSTICK_ID = 0          # Genellikle 0'dır, takılı kontrolcünüzün ID'si
LOOP_DELAY = 0.05        # Ana döngü gecikmesi (saniyede 20 güncelleme için 0.05)

# --- ARDUINO SERİ HABERLEŞME AYARLARI (Manuel Kontrol) ---
# Rover motorlarını kontrol eden Arduino'nun bağlı olduğu seri port
SERIAL_PORT_ARDUINO = '/dev/ttyACM0'  
BAUD_RATE_ARDUINO = 9600              # Arduino kodunuzdaki baud rate ile aynı olmalı
arduino_ser = None # Arduino seri bağlantı nesnesi

# --- OPTITRACK SERİ HABERLEŞME AYARLARI (Veri Okuma) ---
# GPIO 14/15'e bağlı HC-05 modülünün seri portu (OptiTrack verisi için)
SERIAL_PORT_OPTITRACK = '/dev/serial0' 
BAUD_RATE_OPTITRACK = 38400            # OptiTrack göndericisindeki baud rate ile aynı olmalı
optitrack_ser = None # OptiTrack seri bağlantı nesnesi

# --- Joystick Nesnesi ---
joystick = None

def setup_all_connections():
    """
    Tüm gerekli bağlantıları (Arduino, OptiTrack seri portu ve Joystick) kurar.
    Herhangi bir bağlantı başarısız olursa False döner.
    """
    global arduino_ser, optitrack_ser, joystick
    
    # 1. Arduino Seri Bağlantısı Kurulumu
    print(f"Bilgi: Arduino'ya {SERIAL_PORT_ARDUINO} portundan bağlanılıyor...")
    try:
        arduino_ser = serial.Serial(SERIAL_PORT_ARDUINO, BAUD_RATE_ARDUINO, timeout=1)
        time.sleep(2) # Arduino'nun başlatılması için kısa bir gecikme
        arduino_ser.reset_input_buffer() # Gelen tamponu temizle
        print(f"Başarılı: Arduino'ya {SERIAL_PORT_ARDUINO} portundan bağlanıldı.")
    except serial.SerialException as e:
        print(f"HATA: Arduino'ya bağlanılamadı: {e}")
        print("Lütfen Arduino'nun bağlı olduğundan, port adının ve baud rate'in doğru olduğundan emin olun.")
        return False
        
    # 2. OptiTrack Veri Seri Port Bağlantısı Kurulumu
    print(f"Bilgi: OptiTrack verisi için {SERIAL_PORT_OPTITRACK} portuna bağlanılıyor...")
    try:
        optitrack_ser = serial.Serial(SERIAL_PORT_OPTITRACK, BAUD_RATE_OPTITRACK, timeout=0.1) 
        time.sleep(2) # Portun açılması için kısa bir gecikme
        optitrack_ser.reset_input_buffer() # Gelen tamponu temizle
        print(f"Başarılı: OptiTrack seri portuna ({SERIAL_PORT_OPTITRACK}) bağlanıldı.")
    except serial.SerialException as e:
        print(f"HATA: OptiTrack seri portuna bağlanılamadı: {e}.")
        print("Lütfen Raspberry Pi'nin `config.txt` dosyasındaki seri port ayarlarını (Bluetooth'u devre dışı bırakma) ve HC-05 bağlantılarını kontrol edin.")
        return False

    # 3. Pygame ve Joystick Bağlantısı Kurulumu
    try:
        pygame.init() # Pygame'i başlat
        pygame.joystick.init() # Joystick modülünü başlat
        if pygame.joystick.get_count() > 0: # Takılı joystick var mı kontrol et
            joystick = pygame.joystick.Joystick(JOYSTICK_ID)
            joystick.init() # Joystick'i başlat
            print(f"Başarılı: Kontrolcü bulundu: {joystick.get_name()}")
        else:
            print("HATA: Takılı kontrolcü bulunamadı. Lütfen bir kontrolcü bağlayın.")
            return False
    except pygame.error as e:
        print(f"HATA: Pygame veya kontrolcü başlatılamadı: {e}")
        return False
        
    return True # Tüm bağlantılar başarılı

def send_arduino_command(command):
    """
    Arduino'ya komutları güvenli bir şekilde gönderir.
    Seri bağlantı açıksa komutu yeni satır karakteriyle birlikte gönderir.
    """
    if arduino_ser and arduino_ser.is_open:
        try:
            full_command = command + "\n"
            arduino_ser.write(full_command.encode('utf-8'))
        except serial.SerialException as e:
            print(f"Seri yazma hatası (Arduino): {e}")

def process_optitrack_data(data):
    """
    Gelen OptiTrack verisini Python literal olarak ayrıştırır ve ekrana yazdırır.
    Beklenen format: ( (rot_x,y,z), (pos_x,y,z), current_time )
    """
    try:
        # Gelen string'i doğrudan Python literal olarak değerlendiriyoruz.
        # ast.literal_eval, string'i güvenli bir şekilde Python veri yapısına dönüştürür.
        parsed_data = ast.literal_eval(data.strip()) # Baştaki/sondaki boşlukları temizle
        
        # Gelen formatın bir tuple (rotasyon, konum, zaman) olduğunu varsayıyoruz
        if isinstance(parsed_data, tuple) and len(parsed_data) == 3:
            rotation_tuple = parsed_data[0]
            position_tuple = parsed_data[1]
            current_time = parsed_data[2]

            # Rotasyon verilerini yazdır
            if isinstance(rotation_tuple, tuple) and len(rotation_tuple) == 3:
                rot_x, rot_y, rot_z = rotation_tuple
                print(f"OptiTrack Rotasyon: X={rot_x:.6f}, Y={rot_y:.6f}, Z={rot_z:.6f}")
            else:
                print(f"UYARI: Rotasyon verisi hatalı formatta veya eksik: {rotation_tuple}")

            # Konum verilerini yazdır
            if isinstance(position_tuple, tuple) and len(position_tuple) == 3:
                pos_x, pos_y, pos_z = position_tuple
                print(f"OptiTrack Konum: X={pos_x:.6f}, Y={pos_y:.6f}, Z={pos_z:.6f}")
            else:
                print(f"UYARI: Konum verisi hatalı formatta veya eksik: {position_tuple}")

            # Zaman verisini yazdır
            if isinstance(current_time, (int, float)):
                print(f"OptiTrack Zaman: {current_time:.6f}")
            else:
                print(f"UYARI: Zaman verisi hatalı formatta: {current_time}")

        else:
            print(f"UYARI: Gelen veri beklenmedik bir Python literal formatında. Veri: {data}")

    except (ValueError, SyntaxError, IndexError) as e:
        # ast.literal_eval'den veya ayrıştırma sırasında gelebilecek hataları yakala
        print(f"HATA: OptiTrack veri dönüştürme/ayrıştırma hatası. Geçersiz format: '{data}'. Hata: {e}")


# --- Ana Program Akışı ---
if __name__ == "__main__":
    # Tüm bağlantıları kurmaya çalış, başarısız olursa programdan çık
    if not setup_all_connections():
        sys.exit(1)

    print("\nKontrol ve veri okuma döngüsü başlatıldı. Çıkmak için CTRL+C'ye basın.")
    
    # Joystick komutları için son gönderilen değerleri tutuyoruz
    last_throttle = 1500
    last_steering = 'c'
    
    # OptiTrack seri portundan gelen veriyi satır satır işlemek için tampon
    optitrack_buffer = ""

    try:
        while True:
            # 1. JOYSTICK'TEN GİRİŞLERİ OKU VE ARDUINO'YA GÖNDER
            pygame.event.pump() # Pygame olay kuyruğunu güncelle
            
            # Gaz (Throttle) Kontrolü (F710 Eksen Haritası)
            # Sağ Tetik (Axis 2) ve Sol Tetik (Axis 5) değerlerini 0-1 aralığına dönüştür
            forward_axis = (joystick.get_axis(2) + 1) / 2 
            reverse_axis = (joystick.get_axis(5) + 1) / 2 
            current_throttle = 1500 # Varsayılan olarak nötr (motor durur)

            # Geri vites (sol tetik) ileri vitesten (sağ tetik) daha baskınsa geri git
            if reverse_axis > 0.05 and reverse_axis > forward_axis:
                current_throttle = int(1500 - reverse_axis * 500) # 1000 (tam geri) - 1500 (nötr)
            # İleri vites (sağ tetik) aktifse ileri git
            elif forward_axis > 0.05:
                current_throttle = int(1500 + forward_axis * 500) # 1500 (nötr) - 2000 (tam ileri)
            
            # Direksiyon (Steering) Kontrolü (F710 Eksen Haritası)
            # Sağ Analog Çubuk (Yatay Eksen - Axis 3)
            steer_axis = joystick.get_axis(3) 
            current_steering = last_steering # Varsayılan olarak son direksiyon konumu

            if steer_axis > 0.3: # Belirgin bir şekilde sağa dön
                current_steering = 'r'
            elif steer_axis < -0.3: # Belirgin bir şekilde sola dön
                current_steering = 'l'
            else: # Merkezde
                current_steering = 'c'
            
            # --- Komutları Arduino'ya Gönderme ---
            # Sadece değerler değiştiyse komut göndererek seri portu gereksiz yere meşgul etmiyoruz.
            # abs() ile küçük titreşimleri (deadzone) görmezden geliyoruz.
            if abs(current_throttle - last_throttle) > 5: # Gaz değerinde yeterli değişiklik varsa
                send_arduino_command(f"t{current_throttle}")
                last_throttle = current_throttle

            if current_steering != last_steering: # Direksiyon değeri değiştiyse
                send_arduino_command(f"s{current_steering}")
                last_steering = current_steering

            # 2. OPTITRACK SERİ PORTUNDAN VERİ OKU VE İŞLE
            if optitrack_ser.in_waiting > 0: # Seri portta okunacak veri varsa
                received_bytes = optitrack_ser.read(optitrack_ser.in_waiting) # Gelen tüm baytları oku
                optitrack_buffer += received_bytes.decode('utf-8', errors='ignore') # Tampona ekle

                # Tamponda tamamlanmış bir satır (yeni satır karakteri '\n' ile biten) varsa işle
                while '\n' in optitrack_buffer:
                    line, optitrack_buffer = optitrack_buffer.split('\n', 1) # İlk satırı al ve tamponu güncelle
                    line = line.strip() 
                    if line: # Boş satırları atla
                        process_optitrack_data(line) # Gelen OptiTrack verisini işle ve yazdır
            
            # --- DÖNGÜYÜ YAVAŞLATMA ---
            time.sleep(LOOP_DELAY) # CPU kullanımını düşürmek için kısa bir bekleme

    except KeyboardInterrupt:
        print("\nProgram sonlandırılıyor. Bağlantılar kapatılıyor.")
    finally:
        # Program sonlandığında tüm bağlantıları kapat ve araçları güvenle durdur
        print("Son komutlar gönderiliyor (araç durduruluyor)...")
        send_arduino_command("t1500") # Motoru nötr konuma getir
        send_arduino_command("sc")    # Direksiyonu ortaya al
        
        # Arduino seri portunu kapat
        if arduino_ser and arduino_ser.is_open:
            arduino_ser.close()
            print("Arduino seri portu kapatıldı.")
            
        # OptiTrack seri portunu kapat
        if optitrack_ser and optitrack_ser.is_open:
            optitrack_ser.close()
            print("OptiTrack seri portu kapatıldı.")
            
        pygame.quit() # Pygame'i kapat
        print("Tüm bağlantılar kapatıldı. Güle güle!")
        sys.exit(0)
