import serial
import time
import sys

# --- AYARLAR ---
# HC-05'in bağlı olduğu Raspberry Pi'nin seri portu.
# Onboard Bluetooth devre dışı bırakıldığında bu adresi kullanırız.
SERIAL_PORT = '/dev/serial0' 
BAUD_RATE = 38400 # Baud rate'i kendi modülünüzün hızına göre ayarlayın

# Seri Port Nesnesi
ser = None

def setup_serial_connection():
    """Seri port bağlantısını kurar."""
    global ser
    print(f"{SERIAL_PORT} portuna bağlanmaya çalışılıyor...")
    try:
        # timeout=0.1: Veri gelene kadar sonsuza kadar beklememesini sağlar.
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1) 
        time.sleep(2) # Portun açılması için kısa bir gecikme
        ser.reset_input_buffer() # Önceki tamponda kalmış verileri temizle
        print(f"Seri porta ({SERIAL_PORT}) başarıyla bağlanıldı.")
        return True
    except serial.SerialException as e:
        print(f"HATA: Seri porta bağlanılamadı: {e}. Lütfen port adını ve ayarları kontrol edin.")
        return False

def process_and_print_position_data(data):
    """Gelen (x,y,z) verisini ayrıştırır ve ekrana yazdırır."""
    try:
        # Gelen string'den parantezleri ve boşlukları temizle
        cleaned_data = data.strip('()\n\r ')
        
        # String'i virgüllerden ayırarak bir liste oluştur
        coords = cleaned_data.split(',')

        # Eğer tam olarak 3 adet koordinat varsa
        if len(coords) == 3:
            # Her bir değeri float'a çevir
            x = float(coords[0].strip())
            y = float(coords[1].strip())
            z = float(coords[2].strip())
            
            print(f"Alınan Konum: X={x:.2f}, Y={y:.2f}, Z={z:.2f}")
        else:
            print(f"UYARI: Konum verisi ayrıştırma hatası. Beklenmedik format: {data}")
    except (ValueError, IndexError) as e:
        # float'a çevirme hatası veya liste indeksi hatası yakalanır
        print(f"HATA: Veri dönüştürme hatası. Geçersiz format: {data}. Hata: {e}")
        

# --- Ana Program Akışı ---
if __name__ == "__main__":
    if not setup_serial_connection():
        sys.exit(1)

    print("\nHC-05'ten (x,y,z) formatında konum verisi bekleniyor.")
    print("Çıkmak için CTRL+C'ye basın.")

    received_buffer = "" # Seri porttan gelen veriyi tutmak için tampon

    try:
        while True:
            # Seri portta okunacak veri varsa
            if ser.in_waiting > 0:
                received_bytes = ser.read(ser.in_waiting)
                # Gelen baytları string'e çevir
                received_buffer += received_bytes.decode('utf-8', errors='ignore')

                # Tamponda tamamlanmış bir satır varsa işle
                while '\n' in received_buffer:
                    line, received_buffer = received_buffer.split('\n', 1)
                    line = line.strip() 
                    if line:
                        process_and_print_position_data(line)
            
            time.sleep(0.01) # CPU kullanımını düşür

    except KeyboardInterrupt:
        print("\nProgram sonlandırılıyor.")
    finally:
        if ser and ser.is_open:
            ser.close()
            print("Seri port kapatıldı.")
        print("Güle güle!")
        sys.exit(0)
