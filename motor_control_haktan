import pygame
import serial
import time

# --- AYARLAR ---
SERIAL_PORT = '/dev/ttyACM0'  # Arduino'nuzun bağlı olduğu port
BAUD_RATE = 9600              # Arduino kodunuzdaki ile aynı olmalı
LOOP_DELAY = 0.05             # Saniyede 20 (1/0.05) güncelleme. CPU kullanımını düşürür.
JOYSTICK_ID = 0               # Genellikle 0'dır, bilgisayarınızda farklıysa değiştirin.

# --- Arduino ile Seri Haberleşmeyi Başlatma ---
arduino = None
try:
    # timeout=1 eklemek, Arduino'dan veri beklerken programın kilitlenmesini önler.
    arduino = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    # Arduino'nun resetlenmesi ve seri portu dinlemeye başlaması için zaman tanı
    time.sleep(2)
    arduino.reset_input_buffer()
    print(f"Arduino'ya {SERIAL_PORT} portundan başarıyla bağlanıldı.")
except serial.SerialException as e:
    print(f"HATA: Arduino'ya bağlanılamadı: {e}")
    print("Program sonlandırılıyor. Portun doğru olduğundan ve Arduino'nun bağlı olduğundan emin olun.")
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
    print("Program sonlandırılıyor. Kontrolcünün bağlı olduğundan emin olun.")
    exit()

def send_command(command):
    """Arduino'ya komutları güvenli bir şekilde gönderir."""
    if arduino and arduino.is_open:
        try:
            # Komutun sonuna bir newline karakteri (\n) eklemek, Arduino'da veriyi
            # okumayı kolaylaştırır (readStringUntil('\n')).
            full_command = command + "\n"
            arduino.write(full_command.encode('utf-8'))
            # print(f"Gönderildi: {full_command.strip()}") # Hata ayıklama için bu satırı açabilirsiniz
        except serial.SerialException as e:
            print(f"Seri yazma hatası: {e}")
    else:
        print("Arduino bağlantısı kapalı, komut gönderilemiyor.")


# --- Ana Kontrol Döngüsü ---
last_throttle = 1500
last_steering = 'c' # 'l' (sol), 'r' (sağ), 'c' (merkez)

print("Kontrol döngüsü başlatıldı. Çıkmak için CTRL+C'ye basın.")

try:
    while True:
        # Pygame olaylarını işle, bu satır olmadan joystick verileri güncellenmez.
        pygame.event.pump()

        # --- Gaz (Throttle) Kontrolü ---
        # Eksen değerlerini -1 ile 1 arasından 0 ile 1 arasına getiriyoruz.
        forward_axis = (joystick.get_axis(5) + 1) / 2  # Sağ Tetik (RT)
        reverse_axis = (joystick.get_axis(4) + 1) / 2  # Sol Tetik (LT)

        current_throttle = 1500 # Varsayılan olarak nötr

        # Geri vites, ileri vitesten daha baskınsa geri git
        if reverse_axis > 0.05 and reverse_axis > forward_axis:
            # Değeri 1500 (nötr) ile 1000 (tam geri) arasına haritala
            current_throttle = int(1500 - reverse_axis * 500)
        # İleri vites aktifse ileri git
        elif forward_axis > 0.05:
            # Değeri 1500 (nötr) ile 2000 (tam ileri) arasına haritala
            current_throttle = int(1500 + forward_axis * 500)

        # --- Direksiyon (Steering) Kontrolü ---
        steer_axis = joystick.get_axis(0) # Sol Analog Çubuk (Yatay Eksen)
        current_steering = last_steering

        if steer_axis > 0.5: # Belirgin bir şekilde sağa çekilmişse
            current_steering = 'r'
        elif steer_axis < -0.5: # Belirgin bir şekilde sola çekilmişse
            current_steering = 'l'
        else: # Merkezde ise
            current_steering = 'c'
        
        # --- Komutları Gönderme ---
        # Sadece değerler değiştiyse komut gönder. Bu, seri port trafiğini azaltır.
        if current_throttle != last_throttle:
            send_command(f"t{current_throttle}")
            last_throttle = current_throttle

        if current_steering != last_steering:
            send_command(f"s{current_steering}")
            last_steering = current_steering

        # --- DÖNGÜYÜ YAVAŞLATMA (EN ÖNEMLİ KISIM) ---
        # Bu bekleme, CPU'nun %100'de çalışmasını engeller ve ısınmayı önler.
        # 0.05 saniye, saniyede 20 güncelleme demektir ki bu bir RC araba için fazlasıyla yeterlidir.
        time.sleep(LOOP_DELAY)

except KeyboardInterrupt:
    # Program CTRL+C ile kapatıldığında motorları durdur ve bağlantıyı kapat.
    print("\nProgram sonlandırılıyor. Motorlar durduruluyor.")
    send_command("t1500") # Motoru nötr konuma getir
    send_command("sc")    # Direksiyonu ortaya al
    if arduino and arduino.is_open:
        arduino.close()
    pygame.quit()
    print("Bağlantı kapatıldı. Güle güle!")
