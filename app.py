from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import serial
import threading
import time
from twilio.rest import Client
import serial.tools.list_ports
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)

# Serial setup
SERIAL_PORT = os.getenv('SERIAL_PORT')
ser = None

# Twilio credentials
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
TO_PHONE_NUMBER = os.getenv('TO_PHONE_NUMBER')

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# State variables
vibration_value = 0
alert_needed = False
alert_sent = False
confirmation_time_left = 0
threshold = 218
confirmation_duration = 30
confirmation_timer = None
driver_confirmed_safe = False
accident_latitude = None
accident_longitude = None

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/status')
def status():
    print(f"[DEBUG] Flask status route - vibration: {vibration_value}")
    return jsonify({
        'vibration': vibration_value,
        'alert_needed': alert_needed,
        'alert_sent': alert_sent,
        'confirmation_time_left': confirmation_time_left
    })

@app.route('/confirm_safe', methods=['POST'])
def confirm_safe():
    global alert_needed, alert_sent, confirmation_time_left, driver_confirmed_safe
    if alert_sent:
        return jsonify({'message': 'Alert already sent. No action needed.'})
    
    driver_confirmed_safe = True
    alert_needed = False
    alert_sent = False
    confirmation_time_left = 0
    return jsonify({'message': 'Driver confirmed safe. No alert will be sent.'})

def find_available_ports():
    ports = list(serial.tools.list_ports.comports())
    available_ports = [port.device for port in ports]
    print(f"Available ports: {available_ports}")
    return available_ports

def open_serial_connection():
    global ser
    available_ports = find_available_ports()
    if SERIAL_PORT in available_ports:
        ser = serial.Serial(SERIAL_PORT, 9600)
        print(f"Connected to {SERIAL_PORT}")
    else:
        print(f"Port {SERIAL_PORT} not found!")

def read_vibration():
    global vibration_value, alert_needed, confirmation_time_left, alert_sent, confirmation_timer, driver_confirmed_safe
    while True:
        try:
            if ser and ser.in_waiting > 0:
                line = ser.readline().decode('utf-8').strip()
                print(f"[DEBUG] Raw serial line: {line}")

                if "accident detected" in line.lower():
                    location_data = line.split('location: ')[-1]
                    latitude, longitude = location_data.strip("()").split(", ")
                    print(f"Accident detected! Location: {latitude}, {longitude}")
                    alert_needed = True
                    driver_confirmed_safe = False
                    confirmation_time_left = confirmation_duration
                    start_confirmation_timer()
                    global accident_latitude, accident_longitude
                    accident_latitude = latitude
                    accident_longitude = longitude
                elif line.isdigit():
                    vibration_value = int(line)
                    print(f"[DEBUG] Updated vibration value: {vibration_value}")
                else:
                    print("[WARNING] Ignored non-numeric line:", line)
        except Exception as e:
            print("[ERROR] Serial read error:", e)
        time.sleep(0.1)

def start_confirmation_timer():
    global confirmation_timer
    confirmation_timer = threading.Thread(target=confirmation_countdown)
    confirmation_timer.start()

def confirmation_countdown():
    global alert_needed, alert_sent, confirmation_time_left, driver_confirmed_safe
    while confirmation_time_left > 0 and not driver_confirmed_safe:
        time.sleep(1)
        confirmation_time_left -= 1
    if alert_needed and not driver_confirmed_safe:
        send_alert_message()
        alert_sent = True
    alert_needed = False

def send_alert_message():
    try:
        maps_link = f"https://maps.google.com/?q={accident_latitude},{accident_longitude}"
        message_body = f"🚨 Accident detected! No response from driver 💔.\nLive location: {maps_link}"

        message = client.messages.create(
            body=message_body,
            from_=TWILIO_PHONE_NUMBER,
            to=TO_PHONE_NUMBER
        )
        print("Alert sent:", message.sid)
    except Exception as e:
        print("Error sending Twilio SMS:", e)

if __name__ == '__main__':
    open_serial_connection()
    threading.Thread(target=read_vibration, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)
