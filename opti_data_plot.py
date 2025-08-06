# Gerekli kütüphaneleri içe aktarıyoruz
import serial
import time
import sys
import ast # Python literal string'lerini güvenli bir şekilde değerlendirmek için
import matplotlib.pyplot as plt # Grafik çizimi için
from collections import deque # Veri noktalarını verimli bir şekilde saklamak için

# --- AYARLAR ---
# HC-05'in bağlı olduğu Raspberry Pi'nin seri portu.
# Onboard Bluetooth devre dışı bırakıldığında bu adresi kullanırız.
SERIAL_PORT = '/dev/serial0' 
BAUD_RATE = 38400 # Baud rate'i, gönderici ve HC-05 modülünüzün hızıyla aynı olmalı

# Seri Port nesnesi için bir global değişken tanımlıyoruz
ser = None

# --- Grafik Verileri İçin Deque'ler ---
# deque, verimli bir şekilde eleman ekleyip çıkarmak için kullanılır (FIFO - İlk Giren İlk Çıkar)
MAX_PLOT_POINTS = 200    # Grafikte gösterilecek maksimum veri noktası sayısı
x_data = deque(maxlen=MAX_PLOT_POINTS)
y_data = deque(maxlen=MAX_PLOT_POINTS)

# --- Matplotlib Grafik Ayarları ---
fig, ax = plt.subplots(figsize=(8, 6)) # Grafik penceresi ve eksenleri oluştur
line, = ax.plot([], [], 'b-') # Mavi çizgi oluştur, başlangıçta boş
ax.set_title("OptiTrack Konum Takibi (X vs Y)")
ax.set_xlabel("X Konumu")
ax.set_ylabel("Y Konumu")
ax.grid(True) # Izgara ekle
# Grafiğin etkileşimli modda çalışmasını sağla (seri okumayı engellemez)
plt.ion() 
plt.show(block=False) # Grafiği göster ama programı engelleme


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
    Gelen [rotasyon, konum, zaman] verisini ayrıştırır ve ekrana yazdırır.
    Ayrıca konum verilerini grafik için saklar.
    Beklenen format: ( (rot_x,y,z), (pos_x,y,z), current_time )
    """
    try:
        # Gelen string'i doğrudan Python literal olarak değerlendiriyoruz.
        parsed_data = ast.literal_eval(data.strip()) 
        
        if isinstance(parsed_data, tuple) and len(parsed_data) == 3:
            rotation_tuple = parsed_data[0]
            position_tuple = parsed_data[1]
            current_time = parsed_data[2]

            # Rotasyon verilerini yazdır
            if isinstance(rotation_tuple, tuple) and len(rotation_tuple) == 3:
                rot_x, rot_y, rot_z = rotation_tuple
                # print(f"Alınan Rotasyon: X={rot_x:.6f}, Y={rot_y:.6f}, Z={rot_z:.6f}") # İsteğe bağlı, çok fazla çıktı olabilir
            else:
                print(f"UYARI: Rotasyon verisi hatalı formatta veya eksik: {rotation_tuple}")

            # Konum verilerini yazdır ve grafik için sakla
            if isinstance(position_tuple, tuple) and len(position_tuple) == 3:
                pos_x, pos_y, pos_z = position_tuple
                print(f"Alınan Konum: X={pos_x:.6f}, Y={pos_y:.6f}, Z={pos_z:.6f}")
                
                # Konum verilerini grafik için deque'lere ekle
                x_data.append(pos_x)
                y_data.append(pos_y)

            else:
                print(f"UYARI: Konum verisi hatalı formatta veya eksik: {position_tuple}")

            # Zaman verisini yazdır
            if isinstance(current_time, (int, float)):
                # print(f"Alınan Zaman: {current_time:.6f}") # İsteğe bağlı
                pass
            else:
                print(f"UYARI: Zaman verisi hatalı formatta: {current_time}")

        else:
            print(f"UYARI: Gelen veri beklenmedik bir Python literal formatında. Veri: {data}")

    except (ValueError, SyntaxError, IndexError) as e:
        print(f"HATA: Veri dönüştürme/ayrıştırma hatası. Geçersiz format: '{data}'. Hata: {e}")

def update_plot():
    """Grafiği günceller."""
    if x_data and y_data: # Veri varsa
        line.set_data(list(x_data), list(y_data)) # Çizgi verilerini güncelle
        
        # Eksen limitlerini otomatik olarak ayarla (veriye göre)
        # Küçük bir boşluk bırakarak verilerin kenara yapışmasını engelle
        x_min, x_max = min(x_data), max(x_data)
        y_min, y_max = min(y_data), max(y_data)
        
        # Eğer aralık çok küçükse veya tek bir nokta varsa, varsayılan bir aralık kullan
        # Bu, grafiğin başlangıçta donuk kalmasını engeller
        x_range = x_max - x_min
        y_range = y_max - y_min

        if x_range < 0.1: 
            x_range = 0.2
            x_min -= 0.1 # Merkezde kalması için
        if y_range < 0.1: 
            y_range = 0.2
            y_min -= 0.1 # Merkezde kalması için


        ax.set_xlim(x_min - x_range * 0.1, x_max + x_range * 0.1)
        ax.set_ylim(y_min - y_range * 0.1, y_max + y_range * 0.1)
        
        fig.canvas.draw_idle() # Grafiği yeniden çizmesi için işaretle
        fig.canvas.flush_events() # Olayları işle (grafiğin güncellenmesini sağlar)


# --- Ana Program Akışı ---
if __name__ == "__main__":
    if not setup_serial_connection():
        # Bağlantı kurulamazsa programdan çık
        sys.exit(1)

    print("\nHC-05'ten [rotasyon, konum, zaman] formatında verisi bekleniyor.")
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
                    if line: # Boş satırları atla
                        process_and_print_position_data(line)
            
            # Grafiği güncelle
            update_plot()

            time.sleep(0.01) # CPU kullanımını düşürmek için kısa bir bekleme

    except KeyboardInterrupt:
        print("\nProgram sonlandırılıyor.")
    finally:
        # Program sonlandığında seri portu kapat
        if ser and ser.is_open:
            ser.close()
            print("Seri port kapatıldı.")
        
        plt.close(fig) # Grafik penceresini kapat
        print("Güle güle!")
        sys.exit(0)
