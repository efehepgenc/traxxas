import pygame
import serial
import time
import sys

# --- GENEL AYARLAR ---
JOYSTICK_ID = 0          # Genellikle 0'dır
LOOP_DELAY = 0.05        # Saniyede 20 (1/0.05) güncelleme. CPU kullanımını düşürür.

# --- ARDUINO SERİ HABERLEŞME AYARLARI (Manuel Kontrol) ---
SERIAL_PORT_ARDUINO = '/dev/ttyACM0'  # Arduino'nun bağlı olduğu port
BAUD_RATE_ARDUINO = 9600              # Arduino kodunuzdaki ile aynı olmalı
arduino_ser = None

# --- OPTITRACK SERİ HABERLEŞME AYARLARI (Veri Okuma) ---
SERIAL_PORT_OPTITRACK = '/dev/serial0' # GPIO 14/15'e bağlı HC-05 için
BAUD_RATE_OPTITRACK = 38400            # OptiTrack göndericisindeki baud rate ile aynı olmalı
optitrack_ser = None

# --- Joystick ve Pygame Ayarları ---
joystick = None

def setup_all_connections():
    """Tüm bağlantıları (Arduino, OptiTrack ve Joystick) kurar."""
    
    global arduino_ser, optitrack_ser, joystick
    
    # 1. ARDUINO BAĞLANTISI
    print(f"Bilgi: Arduino'ya {SERIAL_PORT_ARDUINO} portundan bağlanılıyor...")
    try:
        arduino_ser = serial.Serial(SERIAL_PORT_ARDUINO, BAUD_RATE_ARDUINO, timeout=1)
        time.sleep(2)
        arduino_ser.reset_input_buffer()
        print(f"Başarılı: Arduino'ya {SERIAL_PORT_ARDUINO} portundan bağlanıldı.")
    except serial.SerialException as e:
        print(f"HATA: Arduino'ya bağlanılamadı: {e}")
        print("Lütfen port adını ve baud rate'i kontrol edin.")
        return False
        
    # 2. OPTITRACK SERİ PORT BAĞLANTISI
    print(f"Bilgi: OptiTrack verisi için {SERIAL_PORT_OPTITRACK} portuna bağlanılıyor...")
    try:
        optitrack_ser = serial.Serial(SERIAL_PORT_OPTITRACK, BAUD_RATE_OPTITRACK, timeout=0.1) 
        time.sleep(2)
        optitrack_ser.reset_input_buffer()
        print(f"Başarılı: OptiTrack seri portuna ({SERIAL_PORT_OPTITRACK}) bağlanıldı.")
    except serial.SerialException as e:
        print(f"HATA: OptiTrack seri portuna bağlanılamadı: {e}.")
        print("Lütfen Pi'nin `config.txt` dosyasını ve bağlantıları kontrol edin.")
        return False

    # 3. JOYSTICK BAĞLANTISI
    try:
        pygame.init()
        pygame.joystick.init()
        if pygame.joystick.get_count() > 0:
            joystick = pygame.joystick.Joystick(JOYSTICK_ID)
            joystick.init()
            print(f"Başarılı: Kontrolcü bulundu: {joystick.get_name()}")
        else:
            print("HATA: Takılı kontrolcü bulunamadı.")
            return False
    except pygame.error as e:
        print(f"HATA: Pygame veya kontrolcü başlatılamadı: {e}")
        return False
        
    return True

def send_arduino_command(command):
    """Arduino'ya komutları güvenli bir şekilde gönderir."""
    if arduino_ser and arduino_ser.is_open:
        try:
            full_command = command + "\n"
            arduino_ser.write(full_command.encode('utf-8'))
        except serial.SerialException as e:
            print(f"Seri yazma hatası: {e}")

def process_optitrack_data(data):
    """
    Gelen [rotasyon, konum] verisini ayrıştırır.
    Format hatası durumunda uyarı verir.
    Yeni format: [(x,y,z),(x,y,z)]
    """
    try:
        # Gelen string'den köşeli parantezleri ve boşlukları temizle
        # Örnek: "[(0.1,0.2,0.3),(10.5,20.2,5.0)]" -> "(0.1,0.2,0.3),(10.5,20.2,5.0)"
        cleaned_data = data.strip('[]\n\r ')
        
        # Rotasyon ve konum verilerini ayır
        # Örnek: "(0.1,0.2,0.3),(10.5,20.2,5.0)" -> ["(0.1,0.2,0.3)", "(10.5,20.2,5.0)"]
        parts = cleaned_data.split('),(')
        
        if len(parts) == 2:
            # Rotasyon ve konum string'lerini al
            rotation_str = parts[0].strip('(')
            position_str = parts[1].strip(')')
            
            # Rotasyon koordinatlarını al ve float'a çevir
            rot_coords = [float(c.strip()) for c in rotation_str.split(',')]
            
            # Konum koordinatlarını al ve float'a çevir
            pos_coords = [float(c.strip()) for c in position_str.split(',')]
            
            # Eğer her ikisi de 3 koordinata sahipse ekrana yazdır
            if len(rot_coords) == 3 and len(pos_coords) == 3:
                rot_x, rot_y, rot_z = rot_coords
                pos_x, pos_y, pos_z = pos_coords
                
                print(f"OptiTrack Rotasyon: X={rot_x:.6f}, Y={rot_y:.6f}, Z={rot_z:.6f}")
                print(f"OptiTrack Konum: X={pos_x:.6f}, Y={pos_y:.6f}, Z={pos_z:.6f}")
            else:
                print(f"UYARI: Ayrıştırma hatası. Rotasyon ve/veya konum koordinatları eksik. Veri: {data}")
        else:
            print(f"UYARI: Ayrıştırma hatası. Beklenmedik format: {data}")

    except (ValueError, IndexError) as e:
        # float'a çevirme hatası veya liste indeksi hatası yakalanır
        print(f"HATA: Veri dönüştürme hatası. Geçersiz format: {data}. Hata: {e}")


# --- Ana Program Akışı ---
if __name__ == "__main__":
    if not setup_all_connections():
        sys.exit(1)

    print("\nKontrol ve veri okuma döngüsü başlatıldı. Çıkmak için CTRL+C'ye basın.")
    
    # Joystick komutları için son değerleri tutuyoruz
    last_throttle = 1500
    last_steering = 'c'
    
    # OptiTrack verisi için bir tampon oluşturuyoruz
    optitrack_buffer = ""

    try:
        while True:
            # 1. JOYSTICK'TEN GİRİŞLERİ OKU VE ARDUINO'YA GÖNDER
            pygame.event.pump()
            
            # Gaz (Throttle) Kontrolü
            forward_axis = (joystick.get_axis(2) + 1) / 2
            reverse_axis = (joystick.get_axis(5) + 1) / 2
            current_throttle = 1500
            if reverse_axis > 0.05 and reverse_axis > forward_axis:
                current_throttle = int(1500 - reverse_axis * 500)
            elif forward_axis > 0.05:
                current_throttle = int(1500 + forward_axis * 500)
            
            # Direksiyon (Steering) Kontrolü
            steer_axis = joystick.get_axis(3)
            current_steering = last_steering
            if steer_axis > 0.3:
                current_steering = 'r'
            elif steer_axis < -0.3:
                current_steering = 'l'
            else:
                current_steering = 'c'
            
            # Sadece değerler değiştiyse komut gönder
            if abs(current_throttle - last_throttle) > 5:
                send_arduino_command(f"t{current_throttle}")
                last_throttle = current_throttle
            
            if current_steering != last_steering:
                send_arduino_command(f"s{current_steering}")
                last_steering = current_steering

            # 2. OPTITRACK SERİ PORTUNDAN VERİ OKU VE İŞLE
            if optitrack_ser.in_waiting > 0:
                received_bytes = optitrack_ser.read(optitrack_ser.in_waiting)
                optitrack_buffer += received_bytes.decode('utf-8', errors='ignore')

                while '\n' in optitrack_buffer:
                    line, optitrack_buffer = optitrack_buffer.split('\n', 1)
                    line = line.strip() 
                    if line:
                        process_optitrack_data(line)
            
            # Döngüyü yavaşlat
            time.sleep(LOOP_DELAY)

    except KeyboardInterrupt:
        print("\nProgram sonlandırılıyor. Bağlantılar kapatılıyor.")
    finally:
        # Program sonlandığında tüm bağlantıları kapat ve araçları durdur
        print("Son komutlar gönderiliyor...")
        send_arduino_command("t1500") # Motoru nötr konuma getir
        send_arduino_command("sc")    # Direksiyonu ortaya al
        
        if arduino_ser and arduino_ser.is_open:
            arduino_ser.close()
            print("Arduino seri portu kapatıldı.")
            
        if optitrack_ser and optitrack_ser.is_open:
            optitrack_ser.close()
            print("OptiTrack seri portu kapatıldı.")
            
        pygame.quit()
        print("Güle güle!")
        sys.exit(0)
