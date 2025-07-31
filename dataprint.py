import serial
import time
import sys
# import bluetooth # ARTIK GEREKLİ DEĞİL!

# --- AYARLAR ---
# HC-05'in bağlı olduğu Raspberry Pi'nin seri portu.
# "/dev/serial0" genellikle Bluetooth devre dışı bırakıldıktan sonraki doğru yoldur.
SERIAL_PORT = '/dev/serial0' 
BAUD_RATE = 38400 # HC-05 modülleri ve Konum Arduino'nuzdaki seri baud rate ile aynı olmalı

# Döngü Zamanlaması
LOOP_DELAY_SEC = 0.05 # Saniyede 20 (1/0.05) güncelleme. CPU kullanımını düşürür.

# Seri Port Nesnesi
ser = None

def setup_serial_connection():
    """Seri port bağlantısını kurar."""
    global ser
    print(f"{SERIAL_PORT} portuna bağlanmaya çalışılıyor...")
    try:
        # timeout=0.1: ser.read() fonksiyonunun veri gelene kadar sonsuza kadar beklememesini sağlar.
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1) 
        time.sleep(2) # Portun açılması için kısa bir gecikme (Arduino'lar için bazen gerekli)
        ser.reset_input_buffer() # Önceki tamponda kalmış verileri temizle
        print(f"Seri porta ({SERIAL_PORT}) başarıyla bağlanıldı.")
        return True
    except serial.SerialException as e:
        print(f"HATA: Seri porta bağlanılamadı: {e}. Lütfen port adını, bağlantıları ve 'raspi-config'/'config.txt' ayarlarını kontrol edin.")
        print("Yaygın nedenler: Yanlış port adı, baud rate uyuşmazlığı, seri konsol açık, Bluetooth kapalı değil.")
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

                # Yönü 0-360 arasına normalleştir
                heading = heading % 360
                if heading < 0:
                    heading += 360

                print(f"Alınan Konum: X={x:.2f}, Y={y:.2f}, Z={z:.2f}, Yön={heading:.2f}°")
            else:
                print(f"HATA: Konum verisi ayrıştırma hatası. Geçersiz format: {data}")
                print("Beklenen format: POSX<sayı>Y<sayı>Z<sayı>H<sayı>")

        except (IndexError, ValueError) as e:
            print(f"HATA: Konum verisi ayrıştırma hatası. Geçersiz format: {data}. Hata: {e}")
            print("Beklenen format: POSX<sayı>Y<sayı>Z<sayı>H<sayı>")
    else:
        print(f"UYARI: Bilinmeyen seri veri veya formatı: {data}")

# --- Ana Program Akışı ---
if __name__ == "__main__":
    try:
        # Pygame, Ctrl+C ile düzgün çıkış için. İsteğe bağlıdır.
        import pygame 
        pygame.init()
    except Exception as e:
        print(f"UYARI: Pygame başlatılamadı: {e}. Program sonlandırılırken kontrol için 'Ctrl+C' kullanın.")

    if not setup_serial_connection():
        sys.exit(1)

    print("\nHC-05 (GPIO'ya bağlı) üzerinden konum verisi bekleniyor ve ekrana yazdırılacak.")
    print("Çıkmak için CTRL+C'ye basın.")

    received_buffer = "" # Seri porttan gelen veriyi satır satır işlemek için tampon

    try:
        while True:
            # Seri portta okunacak veri var mı?
            if ser.in_waiting > 0:
                # Gelen tüm baytları oku
                received_bytes = ser.read(ser.in_waiting)
                # Baytları UTF-8 string'e çevir, hata durumunda karakterleri yoksay
                received_buffer += received_bytes.decode('utf-8', errors='ignore') 

                # Tamponda tamamlanmış bir satır varsa işle
                while '\n' in received_buffer:
                    line, received_buffer = received_buffer.split('\n', 1)
                    line = line.strip() # Baştaki/sondaki boşlukları temizle
                    if line: # Boş satırları atla
                        process_and_print_position_data(line)

            # Pygame olaylarını işle (Ctrl+C ile çıkışı sağlamak için)
            pygame.event.pump()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    print("Pygame kapatma olayı algılandı. Çıkış yapılıyor.")
                    raise KeyboardInterrupt # Temiz bir çıkış için

            time.sleep(LOOP_DELAY_SEC) # CPU kullanımını düşür

    except KeyboardInterrupt:
        print("\nProgram sonlandırılıyor.")
    finally:
        # --- Temizlik ---
        print("Temizlik yapılıyor...")
        if ser and ser.is_open:
            ser.close()
            print("Seri port kapatıldı.")
        
        if 'pygame' in sys.modules and pygame.get_init():
             pygame.quit()
        print("Tüm bağlantılar kapatıldı. Güle güle!")
        sys.exit(0)
