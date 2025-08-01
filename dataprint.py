import serial
import time
import sys

# --- AYARLAR ---
# HC-05'in bağlı olduğu Raspberry Pi'nin seri portu.
# Onboard Bluetooth devre dışı bırakıldığında bu adresi kullanırız.
SERIAL_PORT = '/dev/serial0' 
BAUD_RATE = 9600 # Arduino ve HC-05 modülleri arasındaki baud rate ile aynı olmalı

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
    """Gelen konum verisini ayrıştırır ve ekrana yazdırır."""
    if data.startswith("POS"):
        try:
            # 'POSX10.5Y20.2Z5.0H45.0' formatı bekleniyor
            remaining = data[3:] # 'POS' kısmını atla
            
            x_idx = remaining.find('X')
            y_idx = remaining.find('Y')
            z_idx = remaining.find('Z')
            h_idx = remaining.find('H')

            if x_idx != -1 and y_idx != -1 and z_idx != -1 and h_idx != -1:
                x = float(remaining[x_idx+1 : y_idx])
                y = float(remaining[y_idx+1 : z_idx])
                z = float(remaining[z_idx+1 : h_idx])
                heading = float(remaining[h_idx+1 :])
                
                print(f"Alınan Konum: X={x:.2f}, Y={y:.2f}, Z={z:.2f}, Yön={heading:.2f}°")
            else:
                print(f"HATA: Konum verisi ayrıştırma hatası. Geçersiz format: {data}")
        except (IndexError, ValueError) as e:
            print(f"HATA: Konum verisi ayrıştırma hatası. Geçersiz format: {data}. Hata: {e}")
    else:
        print(f"UYARI: Bilinmeyen seri veri veya formatı: {data}")

# --- Ana Program Akışı ---
if __name__ == "__main__":
    if not setup_serial_connection():
        sys.exit(1)

    print("\nHC-05 (GPIO'ya bağlı) üzerinden konum verisi bekleniyor.")
    print("Çıkmak için CTRL+C'ye basın.")

    received_buffer = "" # Seri porttan gelen veriyi tutmak için tampon

    try:
        while True:
            # Seri portta okunacak veri varsa
            if ser.in_waiting > 0:
                received_bytes = ser.read(ser.in_waiting)
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
