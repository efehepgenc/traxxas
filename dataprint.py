import time
import sys
import bluetooth # HC-05 iletişimi için

# --- AYARLAR ---
# Bluetooth HC-05 Haberleşme (Konum Verisi Alan)
# Konum Arduino'suna bağlı HC-05'in MAC adresi
HC05_POS_MAC_ADDRESS = '00:24:09:01:04:8A' # BURAYI KENDİ KONUM HC-05 MAC ADRESİNİZLE DEĞİŞTİRİN!
HC05_POS_PORT = 1 # Genellikle RFCOMM seri portu için 1 kullanılır

# Döngü Zamanlaması
LOOP_DELAY_SEC = 0.05 # Saniyede 20 (1/0.05) güncelleme. CPU kullanımını düşürür.

# Bluetooth Soketi
hc05_pos_socket = None

def setup_hc05_pos_receiver():
    """Konum verisi alan HC-05 bağlantısını kurar."""
    global hc05_pos_socket
    print(f"Konum Alıcı HC-05'e ({HC05_POS_MAC_ADDRESS}) bağlanmaya çalışılıyor...")
    try:
        hc05_pos_socket = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        hc05_pos_socket.connect((HC05_POS_MAC_ADDRESS, HC05_POS_PORT))
        hc05_pos_socket.settimeout(0.1) # Non-blocking read (okurken beklemez)
        print(f"Konum Alıcı HC-05'e başarıyla bağlanıldı.")
        return True
    except bluetooth.btcommon.BluetoothError as e:
        print(f"HATA: Konum Alıcı HC-05'e bağlanılamadı: {e}. Lütfen MAC adresini, eşleşmeyi ve Bluetooth servisini kontrol edin.")
        print("Bağlantı sorunu devam ederse, 'sudo bluetoothctl' komutunu kullanarak HC-05'inizi eşleştirmeyi deneyin.")
        return False

def process_and_print_position_data(data):
    """Bluetooth'tan gelen konum verisini ayrıştırır ve ekrana yazdırır."""
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
        print(f"UYARI: Bilinmeyen Bluetooth verisi veya formatı: {data}")

# --- Ana Program Akışı ---
if __name__ == "__main__":
    try:
        import pygame # Sadece CTRL+C ile çıkış için kullanılıyor
        pygame.init()
    except Exception as e:
        print(f"UYARI: Pygame başlatılamadı: {e}. Program sonlandırılırken kontrol için 'Ctrl+C' kullanın.")

    if not setup_hc05_pos_receiver():
        sys.exit(1)

    print("\nKonum Arduino'sundan Bluetooth verisi bekleniyor ve ekrana yazdırılacak.")
    print("Çıkmak için CTRL+C'ye basın.")

    try:
        while True:
            # Konum Arduino'sundan veri oku (Bluetooth üzerinden)
            try:
                # Küçük veri paketleri için 1024 yeterlidir, ancak gerekirse artırılabilir
                pos_data = hc05_pos_socket.recv(1024).decode('utf-8').strip()
                if pos_data:
                    process_and_print_position_data(pos_data) # Gelen konumu işle ve yazdır
            except bluetooth.btcommon.BluetoothError as e:
                if "timed out" not in str(e): # Timeout hatası normal, diğerlerini yazdır
                    print(f"Konum Alıcı Bluetooth okuma hatası: {e}")
            except Exception as e:
                print(f"Konum verisi alırken beklenmeyen bir hata oluştu: {e}")

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
        if hc05_pos_socket:
            hc05_pos_socket.close()
            print("Konum Alıcı HC-05 soketi kapatıldı.")
        
        if 'pygame' in sys.modules and pygame.get_init():
             pygame.quit()
        print("Tüm bağlantılar kapatıldı. Güle güle!")
        sys.exit(0)
