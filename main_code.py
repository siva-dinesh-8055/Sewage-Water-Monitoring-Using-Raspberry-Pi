import RPi.GPIO as GPIO
import serial
import time
import lcd
from mcp3008 import MCP3008
import Adafruit_DHT  # Import DHT Library for sensor
import requests  # For sending HTTP requests to ThingSpeak

# ThingSpeak Configuration
THINGSPEAK_URL = "https://api.thingspeak.com/update"
WRITE_API_KEY = "3IKCM42FH0OVJ3V3"  # Replace with your actual API key
CHANNEL_ID = "2893860" # Replace with your actual channel ID

# Initialize the sensor and GPIO settings
sensor_name = Adafruit_DHT.DHT11  # we are using the DHT11 sensor
sensor_pin = 4  # The sensor is connected to GPIO17 on Pi
GPIO.setwarnings(False)
ser = serial.Serial('/dev/ttyS0', baudrate=9600, timeout=1.5)  # Adjust COM port and baudrate as needed
#ser1 = serial.Serial('/dev/ttyUSB0', baudrate=9600, timeout=1.5)
phone_number = "+916300369899"
pump1 = 29  #
led = 31  # GPIO
pump2 = 22  # GPIO
trig = 15
echo = 16
redled = 11
greenled = 13

# Setup GPIO
GPIO.setmode(GPIO.BOARD)
GPIO.setup(trig, GPIO.OUT)
GPIO.setup(echo, GPIO.IN)
GPIO.setup(pump1, GPIO.OUT)
GPIO.setup(led, GPIO.OUT)
GPIO.setup(redled, GPIO.OUT)
GPIO.setup(greenled, GPIO.OUT)
GPIO.setup(pump2, GPIO.OUT)
GPIO.output(led, GPIO.HIGH)
GPIO.output(redled, GPIO.LOW)
GPIO.output(greenled, GPIO.LOW)
GPIO.output(pump1, GPIO.LOW)
GPIO.output(pump2, GPIO.LOW)
lcd.display(f"Sewage water", "Monitoring system")

def send_text_message(msg):
    lcd.display("Sending Message..", " ")
    print("Sending Message")
    time.sleep(1)
    ser.write(b'AT\r\n')
    time.sleep(1)
    ser.write(b"AT+CMGF=1\r")
    time.sleep(3)
    ser.write(f"AT+CMGS=\"{phone_number}\"\r".encode())
    msg = f" -= Alert =- \n {msg}"
    print(msg)
    time.sleep(3)
    ser.reset_output_buffer()
    time.sleep(1)
    ser.write(str.encode(msg + chr(26)))
    time.sleep(2)
    lcd.display("Message Sent", " ")
    print("Message Sent")
    time.sleep(10)

def get_distance():
    GPIO.output(trig, True)
    time.sleep(0.00001)  # Send a short pulse to trigger the sensor
    GPIO.output(trig, False)

    # Wait for the echo to start
    while GPIO.input(echo) == 0:
        start_time = time.time()  # Assign start_time when the echo signal is low

    # Wait for the echo to end
    while GPIO.input(echo) == 1:
        end_time = time.time()  # Assign end_time when the echo signal goes high

    pulse_duration = end_time - start_time  # Calculate pulse duration
    distance = round(pulse_duration * 17150, 2)  # Calculate the distance in cm
    return distance


# Function to send data to ThingSpeak
def upload_to_thingspeak(temperature, humidity, ph_value, gas_value, distance):
    try:
        payload = {
            'api_key': WRITE_API_KEY,
            'field1': temperature,  # Field 1: Temperature
            'field2': humidity,     # Field 2: Humidity
            'field3': ph_value,     # Field 3: pH
            'field4': gas_value,    # Field 4: Gas sensor value
            'field5': distance      # Field 5: Distance
        }

        response = requests.get(THINGSPEAK_URL, params=payload)
        
        if response.status_code == 200:
            print("Data successfully uploaded to ThingSpeak")
        else:
            print("Failed to upload data to ThingSpeak")
    except Exception as e:
        print(f"Error uploading to ThingSpeak: {e}")

try:
    while True:
        distance = get_distance()
        print(f"Distance: {distance} cm")
        lcd.display(f"Distance: {distance} cm", " ")
        data1 = ser.readline().decode('utf-8', errors='ignore').strip()
        
        #print(f"data1:{data1}")# this is all values print
        # Read gas sensor value
        adc = MCP3008()
        time.sleep(1)
        gas_value = adc.read(0)
        print(f"Gas: {gas_value}")
        lcd.display(f"Gas: {gas_value}", " ")

        # Read temperature and humidity from DHT11 sensor
        humidity, temperature = Adafruit_DHT.read_retry(sensor_name, sensor_pin)  # Read from sensor
        print(f"Humidity: {humidity}")
        print(f"Temp: {temperature}")
        lcd.display(f"Temp: {temperature}C", f"Humi: {humidity}%")
        time.sleep(2)
        data1 = ser.readline().decode('utf-8', errors='ignore').strip()
        if data1.startswith("PH:"):  # Ensure data starts with PH value
            try:
                ph_value = float(data1.split(",")[0].split(":")[1].strip())  # Extract and convert to float
                print(f"PH Value: {ph_value:.2f}")  # Print PH value with 2 decimal places
                lcd.display(f"pH: {ph_value:.2f}", " ")  # Display pH value on LCD
            except ValueError:
                print("Error parsing PH value.") #Read pH value from serial data
        
        

        # Upload data to ThingSpeak
        upload_to_thingspeak(temperature, humidity, ph_value, gas_value, distance)

        # Check if the water quality is good
        if ph_value < 10 and gas_value < 400 and temperature < 32:
            print("Good Water Quality")
            lcd.display("Good Water Quality", " ")
            GPIO.output(greenled, GPIO.HIGH)  # Turn on green LED for good water quality
            GPIO.output(redled, GPIO.LOW)
            GPIO.output(pump1, GPIO.HIGH)  # Turn on pump1
            GPIO.output(pump2, GPIO.LOW)  # Ensure pump2 is off
        elif distance < 10:
            print("Water level low, turning on pump")
            send_text_message(f"Warning! Low water level detected: {distance} cm")
            GPIO.output(greenled, GPIO.LOW)  # Turn off green LED
            GPIO.output(redled, GPIO.HIGH)  # Turn on red LED
            GPIO.output(pump1, GPIO.LOW)  # Turn off pump1
            GPIO.output(pump2, GPIO.HIGH)  # Turn on pump2
            time.sleep(1)
            GPIO.output(pump2, GPIO.LOW) 

        elif gas_value > 800 :  # Example gas threshold value
            print("Bad Water Quality (Gas)")
            send_text_message(f"Warning! High gas level detected: {gas_value}")
            GPIO.output(greenled, GPIO.LOW)  # Turn on green LED for good water quality
            GPIO.output(redled, GPIO.HIGH)
            GPIO.output(pump1, GPIO.LOW)  # Turn off pump1
            GPIO.output(pump2, GPIO.HIGH)  # Turn on pump2 for gardening
            time.sleep(1)
            GPIO.output(pump2, GPIO.LOW) 

        elif temperature > 35:  # Example temperature threshold
            print("Bad Water Quality (Temperature)")
            send_text_message(f"Warning! High temperature detected: {temperature}C")
            GPIO.output(greenled, GPIO.LOW)  # Turn on green LED for good water quality
            GPIO.output(redled, GPIO.HIGH)
            GPIO.output(pump1, GPIO.LOW)  # Turn off pump1
            GPIO.output(pump2, GPIO.HIGH)  # Turn on pump2 for gardening
            time.sleep(1)
            GPIO.output(pump2, GPIO.LOW) 

        elif ph_value >10:  # Example pH threshold (acidic)
            print("Bad Water Quality (pH)")
            send_text_message(f"Warning! Low pH detected: {ph_value:.2f}")
            GPIO.output(greenled, GPIO.LOW)  # Turn on green LED for good water quality
            GPIO.output(redled, GPIO.HIGH)
            GPIO.output(pump1, GPIO.LOW)  # Turn off pump1
            GPIO.output(pump2, GPIO.HIGH)  # Turn on pump2 for gardening
            time.sleep(1)
            GPIO.output(pump2, GPIO.LOW) 
        else:
            print("Normal water")
            GPIO.output(greenled, GPIO.LOW)  # Turn on green LED for good water quality
            GPIO.output(redled, GPIO.LOW)
            GPIO.output(pump1, GPIO.LOW)  # Turn off pump1
            GPIO.output(pump2, GPIO.LOW)  # Turn off pump2

        time.sleep(1)

except KeyboardInterrupt:
    pass

finally:
    GPIO.cleanup()
