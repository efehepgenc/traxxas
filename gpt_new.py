import pygame
import serial
import time
import sys
import threading
import re

# --- AYARLAR ---
ARDUINO_PORT = '/dev/ttyACM0'
ARDUINO_BAUD = 9600
BT_PORT = '/dev/serial0'
BT_BAUD = 38400
JOY_LOOP_HZ = 50            # 50 Hz kontrol döngüsü
BT_READ_SLEEP = 0.005       # BT thread kısa bekleme
PRINT_MAX_HZ = 10           # En fazla 10 Hz veri yazdır
JOYSTICK_ID = 0

# Display settings
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
FONT_SIZE = 20

# --- Global değişkenler ---
arduino = None
bt_serial = None
last_throttle = 1500
last_steering = 'c'

# BT okuma için kalıcı tampon ve yazdırma sınırlayıcı
bt_buffer = ''
last_print_ts = 0.0

# Display variables
display_data = {
    'position': [0.0, 0.0, 0.0],
    'rotation': [0.0, 0.0, 0.0],
    'timestamp': 0.0,
    'throttle': 1500,
    'steering': 'c',
    'last_update': 0.0,
    'data_count': 0
}

# OptiTrack satırı (rot, pos, time) regex (float'ları yakalar)
pattern = re.compile(r'^\(\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*\)\s*,\s*\(\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*\)\s*,\s*([-+]?\d*\.?\d+)\s*$')

# --- Arduino Bağlantısı ---
def setup_arduino():
    global arduino
    try:
        arduino = serial.Serial(ARDUINO_PORT, ARDUINO_BAUD, timeout=0)
        time.sleep(2)
        arduino.reset_input_buffer()
        print(f"[✓] Arduino bağlandı: {ARDUINO_PORT}")
    except serial.SerialException as e:
        print(f"[X] Arduino bağlantı hatası: {e}")
        sys.exit(1)

# --- Bluetooth Bağlantısı (OptiTrack Verisi) ---
def setup_bluetooth():
    global bt_serial
    try:
        bt_serial = serial.Serial(BT_PORT, BT_BAUD, timeout=0)
        time.sleep(2)
        bt_serial.reset_input_buffer()
        print(f"[✓] Bluetooth bağlantısı: {BT_PORT}")
    except serial.SerialException as e:
        print(f"[X] Bluetooth bağlantı hatası: {e}")
        sys.exit(1)

# --- OptiTrack verisini işle ---
def process_and_print_position_data(line: str):
    global last_print_ts, display_data
    m = pattern.match(line)
    if not m:
        return  # bozuk satırı atla
    
    rot = list(map(float, m.group(1, 2, 3)))
    pos = list(map(float, m.group(4, 5, 6)))
    t = float(m.group(7))

    # Update display data
    display_data['rotation'] = rot
    display_data['position'] = pos
    display_data['timestamp'] = t
    display_data['last_update'] = time.time()
    display_data['data_count'] += 1

    now = time.time()
    if now - last_print_ts >= (1.0 / PRINT_MAX_HZ):
        print(f"[OptiTrack] Pos: {pos} | Rot: {rot} | Time: {t:.3f}")
        last_print_ts = now

# --- Bluetooth okuma thread'i ---
def bluetooth_reader():
    global bt_buffer
    while True:
        try:
            if bt_serial is None:
                time.sleep(BT_READ_SLEEP)
                continue
            available = bt_serial.in_waiting
            if available:
                chunk = bt_serial.read(available)
                text = chunk.decode('utf-8', errors='ignore')
                # Yalnızca izinli karakterleri tut (parazit önleme)
                text = re.sub(r'[^0-9\n\r\t\.\,()\-\+\s]', '', text)
                bt_buffer += text

            # Satır bazlı ayırma (tamamlanmamış son parça bt_buffer'da kalır)
            if '\n' in bt_buffer:
                lines = bt_buffer.split('\n')
                bt_buffer = lines[-1]
                for raw in lines[:-1]:
                    s = raw.strip()
                    if not s:
                        continue
                    process_and_print_position_data(s)
        except serial.SerialException:
            # Geçici hata → tamponu temizle ve devam et
            bt_buffer = ''
            try:
                bt_serial.reset_input_buffer()
            except Exception:
                pass
        except Exception:
            # Diğer hatalar sessiz geçilsin (veri akışını kesmeyelim)
            pass
        time.sleep(BT_READ_SLEEP)

# --- Arduino'ya komut gönder ---
def send_command(cmd: str):
    if arduino and arduino.is_open:
        try:
            arduino.write((cmd + '\n').encode('utf-8'))
        except serial.SerialException:
            pass

# --- Display thread'i ---
def display_thread():
    global display_data
    
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Motor Control & OptiTrack Data Monitor")
    font = pygame.font.Font(None, FONT_SIZE)
    title_font = pygame.font.Font(None, FONT_SIZE + 8)
    clock = pygame.time.Clock()
    
    # Colors
    BLACK = (0, 0, 0)
    WHITE = (255, 255, 255)
    GREEN = (0, 255, 0)
    RED = (255, 0, 0)
    BLUE = (0, 0, 255)
    YELLOW = (255, 255, 0)
    GRAY = (128, 128, 128)
    
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
        
        screen.fill(BLACK)
        y_offset = 20
        
        # Title
        title_text = title_font.render("MOTOR CONTROL & OPTITRACK MONITOR", True, WHITE)
        screen.blit(title_text, (20, y_offset))
        y_offset += 50
        
        # Connection status
        arduino_status = "CONNECTED" if arduino and arduino.is_open else "DISCONNECTED"
        bt_status = "CONNECTED" if bt_serial and bt_serial.is_open else "DISCONNECTED"
        
        arduino_color = GREEN if arduino and arduino.is_open else RED
        bt_color = GREEN if bt_serial and bt_serial.is_open else RED
        
        arduino_text = font.render(f"Arduino: {arduino_status}", True, arduino_color)
        bt_text = font.render(f"Bluetooth: {bt_status}", True, bt_color)
        screen.blit(arduino_text, (20, y_offset))
        screen.blit(bt_text, (300, y_offset))
        y_offset += 40
        
        # Separator line
        pygame.draw.line(screen, GRAY, (20, y_offset), (WINDOW_WIDTH - 20, y_offset), 2)
        y_offset += 30
        
        # Motor controls
        motor_title = font.render("MOTOR CONTROLS:", True, YELLOW)
        screen.blit(motor_title, (20, y_offset))
        y_offset += 30
        
        throttle_text = font.render(f"Throttle: {display_data['throttle']}", True, WHITE)
        steering_text = font.render(f"Steering: {display_data['steering']}", True, WHITE)
        screen.blit(throttle_text, (40, y_offset))
        screen.blit(steering_text, (250, y_offset))
        y_offset += 40
        
        # OptiTrack data
        opti_title = font.render("OPTITRACK DATA:", True, YELLOW)
        screen.blit(opti_title, (20, y_offset))
        y_offset += 30
        
        # Data freshness indicator
        data_age = time.time() - display_data['last_update']
        if data_age < 1.0:
            freshness_color = GREEN
            freshness_text = "LIVE"
        elif data_age < 5.0:
            freshness_color = YELLOW
            freshness_text = f"STALE ({data_age:.1f}s)"
        else:
            freshness_color = RED
            freshness_text = f"OLD ({data_age:.1f}s)"
        
        fresh_indicator = font.render(f"Data Status: {freshness_text}", True, freshness_color)
        screen.blit(fresh_indicator, (40, y_offset))
        y_offset += 30
        
        # Position data
        pos_text = font.render("Position (X, Y, Z):", True, BLUE)
        screen.blit(pos_text, (40, y_offset))
        y_offset += 25
        
        pos_x_text = font.render(f"  X: {display_data['position'][0]:8.3f}", True, WHITE)
        pos_y_text = font.render(f"  Y: {display_data['position'][1]:8.3f}", True, WHITE)
        pos_z_text = font.render(f"  Z: {display_data['position'][2]:8.3f}", True, WHITE)
        screen.blit(pos_x_text, (60, y_offset))
        screen.blit(pos_y_text, (250, y_offset))
        screen.blit(pos_z_text, (440, y_offset))
        y_offset += 40
        
        # Rotation data
        rot_text = font.render("Rotation (X, Y, Z):", True, BLUE)
        screen.blit(rot_text, (40, y_offset))
        y_offset += 25
        
        rot_x_text = font.render(f"  X: {display_data['rotation'][0]:8.3f}", True, WHITE)
        rot_y_text = font.render(f"  Y: {display_data['rotation'][1]:8.3f}", True, WHITE)
        rot_z_text = font.render(f"  Z: {display_data['rotation'][2]:8.3f}", True, WHITE)
        screen.blit(rot_x_text, (60, y_offset))
        screen.blit(rot_y_text, (250, y_offset))
        screen.blit(rot_z_text, (440, y_offset))
        y_offset += 40
        
        # Timestamp and stats
        timestamp_text = font.render(f"Timestamp: {display_data['timestamp']:.3f}", True, WHITE)
        count_text = font.render(f"Data Packets: {display_data['data_count']}", True, WHITE)
        screen.blit(timestamp_text, (40, y_offset))
        screen.blit(count_text, (350, y_offset))
        y_offset += 40
        
        # Visual position indicator (simple 2D projection)
        pygame.draw.circle(screen, GRAY, (400, 450), 100, 2)
        pygame.draw.line(screen, GRAY, (300, 450), (500, 450), 1)
        pygame.draw.line(screen, GRAY, (400, 350), (400, 550), 1)
        
        # Draw position dot (scaled down)
        scale = 50
        pos_x_screen = int(400 + display_data['position'][0] * scale)
        pos_y_screen = int(450 - display_data['position'][1] * scale)  # Invert Y for screen coords
        
        # Clamp to circle
        dx = pos_x_screen - 400
        dy = pos_y_screen - 450
        dist = (dx*dx + dy*dy)**0.5
        if dist > 95:  # Keep inside circle
            pos_x_screen = int(400 + (dx/dist) * 95)
            pos_y_screen = int(450 + (dy/dist) * 95)
        
        pygame.draw.circle(screen, GREEN, (pos_x_screen, pos_y_screen), 5)
        
        # Labels for the position display
        pos_display_title = font.render("Position (X-Y Plane)", True, WHITE)
        screen.blit(pos_display_title, (320, 320))
        
        pygame.display.flip()
        clock.tick(30)  # 30 FPS for display

# --- Joystick kontrol thread'i ---
def joystick_control():
    global last_throttle, last_steering, display_data
    try:
        pygame.init()
        pygame.joystick.init()
        js = pygame.joystick.Joystick(JOYSTICK_ID)
        js.init()
        print(f"[✓] Kontrolcü: {js.get_name()}")
    except pygame.error:
        print("[X] Kontrolcü bulunamadı")
        sys.exit(1)

    period = 1.0 / JOY_LOOP_HZ
    next_ts = time.time()

    while True:
        start = time.time()
        pygame.event.pump()

        # Throttle
        fw = (js.get_axis(2) + 1) / 2
        rv = (js.get_axis(5) + 1) / 2
        throttle = 1500
        if rv > 0.05 and rv > fw:
            throttle = int(1500 - rv * 500)
        elif fw > 0.05:
            throttle = int(1500 + fw * 500)
        if abs(throttle - last_throttle) > 5:
            send_command(f"t{throttle}")
            last_throttle = throttle
            display_data['throttle'] = throttle

        # Steering
        sv = js.get_axis(3)
        steer_cmd = 'c'
        if sv > 0.3:
            steer_cmd = 'r'
        elif sv < -0.3:
            steer_cmd = 'l'
        if steer_cmd != last_steering:
            send_command(f"s{steer_cmd}")
            last_steering = steer_cmd
            display_data['steering'] = steer_cmd

        # Sabit frekanslı döngü (joystick)
        next_ts += period
        sleep_for = next_ts - time.time()
        if sleep_for > 0:
            time.sleep(sleep_for)
        else:
            # Fazla geciktiysek bir sonraki adıma geç
            next_ts = time.time()

# === Program Başlangıcı ===
if __name__ == '__main__':
    setup_arduino()
    setup_bluetooth()
    print("Basladi: Motor kontrol (thread) + OptiTrack okuma (thread) + Display")
    print("Görsel ekran açılıyor... Kapatmak için ESC tuşuna basın veya pencereyi kapatın.")

    t_bt = threading.Thread(target=bluetooth_reader, daemon=True)
    t_js = threading.Thread(target=joystick_control, daemon=True)
    t_display = threading.Thread(target=display_thread, daemon=True)
    
    t_bt.start()
    t_js.start()
    t_display.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nKapatiliyor...")
        send_command("t1500")
        send_command("sc")
        try:
            if arduino and arduino.is_open:
                arduino.close()
            if bt_serial and bt_serial.is_open:
                bt_serial.close()
        except Exception:
            pass
        pygame.quit()
        print("Gule gule!")
        sys.exit(0)
