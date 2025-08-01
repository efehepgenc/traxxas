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
    Gelen (x,y,z) verisini ayrıştırır ve ekrana yazdırır.
    Format hatası durumunda uyarı verir.
    """
    try:
        # Gelen string'den parantezleri ve boşlukları temizle
        # Örnek: "(10.5, 20.2, 5.0)" -> "10.5, 20.2, 5.0"
        cleaned_data = data.strip('()\n\r ')
        
        # String'i virgüllerden ayırarak bir liste oluştur
        coords = cleaned_data.split(',')

        # Eğer tam olarak 3 adet koordinat varsa
        if len(coords) == 3:
            # Her bir değeri float'a çeviriyoruz
            x = float(coords[0].strip())
            y = float(coords[1].strip())
            z = float(coords[2].strip())
            
            print(f"Alınan Konum: X={x:.6f}, Y={y:.6f}, Z={z:.6f}")
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

    print("\nHC-05'ten (x,y,z) formatında konum verisi bekleniyor.")
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
