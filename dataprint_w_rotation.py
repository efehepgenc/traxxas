
# Gerekli kütüphaneleri içe aktarıyoruz
import serial
import time
import sys

# --- AYARLAR ---
# HC-05'in bağlı olduğu Raspberry Pi'nin seri portu.
# Onboard Bluetooth devre dışı bırakıldığında bu adresi kullanırız.
SERIAL_PORT = '/dev/serial0' 
BAUD_RATE = 38400 # Baud rate'i, gönderici ve HC-05 modülünüzün hızıyla aynı olmalı

# Seri Port nesnesi için bir global değişken tanımlıyoruz
ser = None

def setup_serial_connection():
    """
    Seri port bağlantısını kurar.
    Başarısız olursa hata mesajı verir.
    """
    global ser
    print(f"Bilgi: {SERIAL_PORT} portuna bağlanmaya çalışılıyor...")
    try:
        # timeout=0.1: Veri gelene kadar sonsuza kadar beklemesini engeller.
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1) 
        time.sleep(2) # Portun açılması için kısa bir gecikme
        ser.reset_input_buffer() # Önceki tamponda kalmış verileri temizle
        print(f"Başarılı: Seri porta ({SERIAL_PORT}) başarıyla bağlanıldı.")
        return True
    except serial.SerialException as e:
        print(f"HATA: Seri porta bağlanılamadı: {e}.")
        print("Lütfen aşağıdaki ayarları kontrol edin:")
        print("  - Port adının doğru olduğundan emin olun.")
        print("  - `raspi-config` ve `config.txt` ayarlarını doğrulayın.")
        return False

def process_and_print_position_data(data):
    """
    Gelen [rotasyon, konum] verisini ayrıştırır ve ekrana yazdırır.
    Format hatası durumunda uyarı verir.
    """
    try:
        # Gelen string'den köşeli parantezleri ve boşlukları temizle
        # Örnek: "[(0.1,0.2,0.3),(10.5,20.2,5.0)]" -> "(0.1,0.2,0.3),(10.5,20.2,5.0)"
        cleaned_data = data.strip('[]\n\r ')
        
        # Rotasyon ve konum verilerini ayır
        # Örnek: "(0.1,0.2,0.3),(10.5,20.2,5.0)" -> ["(0.1,0.2,0.3)", "(10.5,20.2,5.0)"]
        parts = cleaned_data.split('),(')
        
        if len(parts) == 2:
            # Rotasyon ve konum verilerini temizle
            rotation_data = parts[0].strip('(')
            position_data = parts[1].strip(')')
            
            # Rotasyon koordinatlarını al ve float'a çevir
            rot_coords = [float(c.strip()) for c in rotation_data.split(',')]
            
            # Konum koordinatlarını al ve float'a çevir
            pos_coords = [float(c.strip()) for c in position_data.split(',')]
            
            # Eğer her ikisi de 3 koordinata sahipse ekrana yazdır
            if len(rot_coords) == 3 and len(pos_coords) == 3:
                rot_x, rot_y, rot_z = rot_coords
                pos_x, pos_y, pos_z = pos_coords
                
                print(f"Alınan Rotasyon: X={rot_x:.6f}, Y={rot_y:.6f}, Z={rot_z:.6f}")
                print(f"Alınan Konum: X={pos_x:.6f}, Y={pos_y:.6f}, Z={pos_z:.6f}")
            else:
                print(f"UYARI: Ayrıştırma hatası. Rotasyon ve/veya konum koordinatları eksik. Veri: {data}")
        else:
            print(f"UYARI: Konum verisi ayrıştırma hatası. Beklenmedik format: {data}")
    except (ValueError, IndexError) as e:
        # float'a çevirme hatası veya liste indeksi hatası yakalanır
        print(f"HATA: Veri dönüştürme hatası. Geçersiz format: {data}. Hata: {e}")
        

# --- Ana Program Akışı ---
if __name__ == "__main__":
    if not setup_serial_connection():
        # Bağlantı kurulamazsa programdan çık
        sys.exit(1)

    print("\nHC-05'ten [rotasyon, konum] formatında verisi bekleniyor.")
    print("Çıkmak için CTRL+C'ye basın.")

    # Seri porttan gelen veriyi tutmak için bir tampon oluşturuyoruz
    received_buffer = "" 

    try:
        while True:
            # Seri portta okunacak veri varsa
            if ser.in_waiting > 0:
                # Gelen baytları oku ve string'e çevir
                received_bytes = ser.read(ser.in_waiting)
                received_buffer += received_bytes.decode('utf-8', errors='ignore')

                # Tamponda tamamlanmış bir satır varsa işle
                while '\n' in received_buffer:
                    line, received_buffer = received_buffer.split('\n', 1)
                    line = line.strip() 
                    if line:
                        process_and_print_position_data(line)
            
            time.sleep(0.01) # CPU kullanımını düşürmek için kısa bir bekleme

    except KeyboardInterrupt:
        print("\nProgram sonlandırılıyor.")
    finally:
        # Program sonlandığında seri portu kapat
        if ser and ser.is_open:
            ser.close()
            print("Seri port kapatıldı.")
        print("Güle güle!")
        sys.exit(0)
