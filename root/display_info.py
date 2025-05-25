#!/usr/bin/env python3
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas
from PIL import ImageFont
import subprocess
import time
import logging
import sys
import re

# Configuration constants
DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 64
I2C_PORT = 3
I2C_ADDRESS = 0x3C
DISPLAY_UPDATE_INTERVAL = 5  # seconds
DISPLAY_RECONNECT_INTERVAL = 30  # seconds
LOG_FILE = '/tmp/display.log'
FONT_SIZE = 10

font_path = '/usr/share/fonts/ttf-dejavu/DejaVuSans.ttf'
try:
    font = ImageFont.truetype(font_path, size=FONT_SIZE)
except OSError:
    # Fallback to default font if DejaVuSans is not available
    font = ImageFont.load_default()
    logging.warning("Using default font as DejaVuSans.ttf not found")

# Настройка логгирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)

def init_display():
    try:
        serial = i2c(port=I2C_PORT, address=I2C_ADDRESS)
        device = ssd1306(serial, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT)
        logging.info("OLED display initialized successfully")
        return device
    except Exception as e:
        logging.error(f"Display initialization failed: {str(e)}")
        return None

def get_wifi_info(interface):
    if not interface:
        return "No interface", "N/A"
        
    try:
        info = subprocess.getoutput(f"iwinfo {interface} info")
        
        if "No such device" in info:
            logging.error(f"Device {interface} not found")
            return "No device", "N/A"
        
        essid = "N/A"
        if "ESSID:" in info:
            essid_line = [line for line in info.split("\n") if "ESSID:" in line][0]
            essid = essid_line.split("ESSID:")[1].strip().strip('"')
        
        signal = "N/A"
        if "Signal:" in info:
            signal_line = [line for line in info.split("\n") if "Signal:" in line][0]
            signal = signal_line.split("Signal:")[1].split()[0].strip()
        
        return essid, signal
    except IndexError as e:
        logging.error(f"Error parsing WiFi info for {interface}: {str(e)}")
        return "Parse error", "N/A"
    except Exception as e:
        logging.error(f"Error getting WiFi info for {interface}: {str(e)}")
        return "Error", "N/A"
    
def get_ip_info(interface):
    try:
        info = subprocess.getoutput(f"ip addr show {interface}")
        ip = "N/A"
        if "inet " in info:
            ip_line = [line for line in info.split("\n") if "inet " in line][0]
            ip = ip_line.split("inet ")[1].split()[0].strip()

        return ip
    except Exception as e:
        logging.error(f"Error getting IP info: {str(e)}")
        return "Error"

def get_cpu_info():
    try:
        info_usage = subprocess.getoutput("top -b -n 1 | grep 'Cpu(s)'")
        cpu_usage = info_usage.split()[1].strip()

        info_temp = subprocess.getoutput("cat /sys/class/thermal/thermal_zone0/temp")
        temp = int(int(info_temp.strip()) / 1000)

        return cpu_usage, temp
    except (IndexError, ValueError) as e:
        logging.error(f"Error parsing CPU info: {str(e)}")
        return "N/A", 0
    except Exception as e:
        logging.error(f"Error getting CPU info: {str(e)}")
        return "N/A", 0

def find_wifi_interfaces():
    try:
        # Получаем список всех интерфейсов
        interfaces = subprocess.getoutput("iwinfo").split('\n')
        
        # Ищем STA и AP интерфейсы
        sta_interface = None
        ap_interface = None
        
        for line in interfaces:
            if 'phy' in line:
                interface = line.split()[0].strip()
                if '-sta' in interface:
                    sta_interface = interface
                elif '-ap' in interface:
                    ap_interface = interface
        
        return sta_interface, ap_interface
    except Exception as e:
        logging.error(f"Error finding WiFi interfaces: {str(e)}")
        return None, None

def main():
    device = None
    last_reconnect = 0
    
    while True:
        current_time = time.time()
        
        # Проверяем подключение дисплея
        if not device or (current_time - last_reconnect > DISPLAY_RECONNECT_INTERVAL):
            device = init_display()
            last_reconnect = current_time
            
        if device:
            try:
                # Находим активные WiFi интерфейсы
                sta_interface, ap_interface = find_wifi_interfaces()
                
                if not sta_interface or not ap_interface:
                    logging.error("Could not find required WiFi interfaces")
                    client_essid, client_signal = "No STA", "N/A"
                    ap_essid, ap_signal = "No AP", "N/A"
                else:
                    # Получаем информацию о сетях
                    client_essid, client_signal = get_wifi_info(sta_interface)
                    ap_essid, ap_signal = get_wifi_info(ap_interface)
                
                ip_info = get_ip_info("br-lan")
                cpu_usage, temp = get_cpu_info()
                
                # Выводим на экран
                with canvas(device) as draw:
                    y_offset = 0
                    line_height = 12
                    draw.text((0, y_offset), f"Client: {client_essid}", font=font, fill="white")
                    draw.text((0, y_offset + line_height), f"Signal: {client_signal} dBm", font=font, fill="white")
                    draw.text((0, y_offset + line_height * 2), f"AP: {ap_essid}", font=font, fill="white")
                    draw.text((0, y_offset + line_height * 3), f"IP: {ip_info}", font=font, fill="white")
                    draw.text((0, y_offset + line_height * 4), f"Temp: {temp}°C", font=font, fill="white")
                    
            except Exception as e:
                logging.error(f"Display error: {str(e)}")
                device = None  # Принудительная реинициализация
                
        time.sleep(DISPLAY_UPDATE_INTERVAL)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Script stopped by user")
        sys.exit(0)
    except Exception as e:
        logging.critical(f"Fatal error: {str(e)}")
        sys.exit(1) 
