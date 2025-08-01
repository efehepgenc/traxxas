import serial
import time
import sys

# --- AYARLAR ---
SERIAL_PORT = '/dev/serial0' 
BAUD_RATE = 38400

ser = None

def setup_serial_connection():
    """Seri port bağlantısını kurar."""
    global ser
    print(f"Bilgi: {SERIAL_PORT} portuna bağlanmaya çalışılıyor...")
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1) 
        time.sleep(2)
        ser.reset_input_buffer()
        print(f"Başarılı: Seri porta ({SERIAL_PORT}) başarıyla bağlanıldı.")
        return True
    except serial.SerialException as e:
        # Hatanın ne olduğunu daha net görebilmek için hata detayını yazdırıyoruz.
        print(f"HATA: Seri porta bağlanılamadı. Hata detayları: {e}")
        print("Lütfen aşağıdaki maddeleri kontrol edin:")
        print("  - Port adının doğru olduğundan emin olun.")
        print("  - 'raspi-config' ve 'config.txt' ayarlarının doğru olduğundan emin olun.")
        print("  - Kullanıcınızın seri portu kullanma izni olduğundan emin olun. (`sudo usermod -a -G dialout pi`)")
        return False

def process_and_print_position_data(data):
    # ... (Bu fonksiyon aynı kalacak, gelen veriyi ayrıştırır)
    try:
        cleaned_data = data.strip('()\n\r ')
        coords = cleaned_data.split(',')
        if len(coords) == 3:
            x = float(coords[0].strip())
            y = float(coords[1].strip())
            z = float(coords[2].strip())
            print(f"Alınan Konum: X={x:.2f}, Y={y:.2f}, Z={z:.2f}")
        else:
            print(f"UYARI: Konum verisi ayrıştırma hatası. Beklenmedik format: {data}")
    except (ValueError, IndexError) as e:
        print(f"HATA: Veri dönüştürme hatası. Geçersiz format: {data}. Hata: {e}")


if __name__ == "__main__":
    if not setup_serial_connection():
        sys.exit(1)

    print("\nHC-05'ten (x,y,z) formatında konum verisi bekleniyor.")
    print("Çıkmak için CTRL+C'ye basın.")

    received_buffer = ""

    try:
        while True:
            if ser.in_waiting > 0:
                received_bytes = ser.read(ser.in_waiting)
                received_buffer += received_bytes.decode('utf-8', errors='ignore')
                while '\n' in received_buffer:
                    line, received_buffer = received_buffer.split('\n', 1)
                    line = line.strip() 
                    if line:
                        process_and_print_position_data(line)
            
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nProgram sonlandırılıyor.")
    finally:
        if ser and ser.is_open:
            ser.close()
            print("Seri port kapatıldı.")
        print("Güle güle!")
        sys.exit(0)
