import pygame
import serial
import time

# --- AYARLAR ---
SERIAL_PORT = '/dev/ttyACM0'  # Arduino'nuzun bağlı olduğu port
BAUD_RATE = 9600              # Arduino kodunuzdaki ile aynı olmalı
LOOP_DELAY = 0.05             # Saniyede 20 (1/0.05) güncelleme. CPU kullanımını düşürür.
JOYSTICK_ID = 0               # Genellikle 0'dır

# --- Arduino ile Seri Haberleşmeyi Başlatma ---
arduino = None
try:
    arduino = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2) # Arduino'nun kendine gelmesi için zaman tanı
    arduino.reset_input_buffer()
    print(f"Arduino'ya {SERIAL_PORT} portundan başarıyla bağlanıldı.")
except serial.SerialException as e:
    print(f"HATA: Arduino'ya bağlanılamadı: {e}")
    exit()

# --- Pygame ve Joystick'i Başlatma ---
try:
    pygame.init()
    pygame.joystick.init()
    joystick = pygame.joystick.Joystick(JOYSTICK_ID)
    joystick.init()
    print(f"Kontrolcü bulundu: {joystick.get_name()}")
except pygame.error as e:
    print(f"HATA: Kontrolcü bulunamadı: {e}")
    exit()

def send_command(command):
    """Arduino'ya komutları güvenli bir şekilde gönderir."""
    if arduino and arduino.is_open:
        try:
            full_command = command + "\n"
            arduino.write(full_command.encode('utf-8'))
        except serial.SerialException as e:
            print(f"Seri yazma hatası: {e}")

# --- Başlangıç Değerleri ---
last_throttle = 1500
last_steering = 'c'

print("Kontrol döngüsü başlatıldı. Çıkmak için CTRL+C'ye basın.")

try:
    while True:
        pygame.event.pump()

        # --- Gaz (Throttle) Kontrolü - F710 Eksen Haritası ---
        # Eksen değerlerini (-1 to 1) aralığından (0 to 1) aralığına getiriyoruz.
        # Orijinal kodunuzdaki eksen numaraları kullanıldı.
        forward_axis = (joystick.get_axis(2) + 1) / 2  # Sağ Tetik (RT)
        reverse_axis = (joystick.get_axis(5) + 1) / 2  # Sol Tetik (LT)
        
        current_throttle = 1500 # Varsayılan olarak nötr

        # Geri vites, ileri vitesten daha baskınsa geri git
        if reverse_axis > 0.05 and reverse_axis > forward_axis:
            current_throttle = int(1500 - reverse_axis * 500)
        # İleri vites aktifse ileri git
        elif forward_axis > 0.05:
            current_throttle = int(1500 + forward_axis * 500)

        # --- Direksiyon (Steering) Kontrolü - F710 Eksen Haritası ---
        # Orijinal kodunuzdaki eksen numarası kullanıldı.
        steer_axis = joystick.get_axis(3) # Sağ Analog Çubuk (Yatay Eksen)
        current_steering = last_steering

        if steer_axis > 0.3: # Belirgin bir şekilde sağa
            current_steering = 'r'
        elif steer_axis < -0.3: # Belirgin bir şekilde sola
            current_steering = 'l'
        else: # Merkezde
            current_steering = 'c'
        
        # --- Komutları Gönderme ---
        # Sadece değerler değiştiyse komut göndererek seri portu meşgul etmiyoruz.
        # abs() ile küçük titreşimleri görmezden geliyoruz.
        if abs(current_throttle - last_throttle) > 5:
            send_command(f"t{current_throttle}")
            last_throttle = current_throttle

        if current_steering != last_steering:
            send_command(f"s{current_steering}")
            last_steering = current_steering

        # --- DÖNGÜYÜ YAVAŞLATMA (ISINMAYI ÖNLEYEN KISIM) ---
        time.sleep(LOOP_DELAY)

except KeyboardInterrupt:
    print("\nProgram sonlandırılıyor. Araç durduruluyor.")
    send_command("t1500") # Motoru nötr konuma getir
    send_command("sc")    # Direksiyonu ortaya al
    if arduino and arduino.is_open:
        arduino.close()
    pygame.quit()
    print("Bağlantı kapatıldı. Güle güle!")
