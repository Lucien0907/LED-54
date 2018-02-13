import time
from machine import Pin, I2C, PWM, RTC
from umqtt.simple import MQTTClient
import ujson
import machine
import network
import ubinascii
import micropython

#----------------------------------------Pin Specification--------------------------------------#

i2c = I2C(scl = Pin(5), sda = Pin(4), freq = 100000)
i2c.writeto_mem(0x39, 0x0, bytearray([0x03]))
i2c.writeto_mem(0x40, 0x2, bytearray([0x1140]))
pwm = PWM(Pin(14))
servo = machine.PWM(machine.Pin(12),freq = 50)

rtc= machine.RTC()
rtc.datetime((2018, 2, 7, 3, 17, 51, 0, 0))

#------------------------------------------State Preset-----------------------------------------#

state = 1
temp_state = 0
var = 2**15
#---------------------------------------Function Definition-------------------------------------#

# Get data from the light sensor and return the value in Lux
def lux_sensor():
        time.sleep(0.4)
        data1=i2c.readfrom_mem(0x39, 0xAC, 2)
        Ch0=(int.from_bytes(data1, 'little'))

        data2=i2c.readfrom_mem(0x39, 0xAE, 2)
        Ch1=(int.from_bytes(data2, 'little'))

        if Ch1/Ch0 >= 0.00 and Ch1/Ch0 < 0.50:
            Lux = Ch0*(0.0304 - 0.062*((Ch1/Ch0)**1.4))
    
            if Ch1/Ch0 >= 0.00 and Ch1/Ch0 < 0.125:
                Lux = Ch0*(0.0304 - 0.0272*(Ch1/Ch0))
        
            if Ch1/Ch0 >= 0.125 and Ch1/Ch0 < 0.250:
                Lux = Ch0*(0.0325 - 0.0440*(Ch1/Ch0))
        
            if Ch1/Ch0 >= 0.250 and Ch1/Ch0 < 0.375:
                Lux=Ch0*(0.0351 - 0.0544*(Ch1/Ch0))
        
            if Ch1/Ch0 >= 0.375 and Ch1/Ch0 < 0.50:
                Lux=Ch0*(0.0381 - 0.0624*(Ch1/Ch0))
     
        if Ch1/Ch0 >= 0.50 and Ch1/Ch0 < 0.61:
            Lux=Ch0*(0.0224 - 0.031*(Ch1/Ch0))
    
        if Ch1/Ch0 >= 0.61 and Ch1/Ch0 < 0.80:
            Lux=Ch0*(0.0128 - 0.0153*(Ch1/Ch0))

        if Ch1/Ch0 >= 0.80 and Ch1/Ch0 < 1.3:
            Lux=Ch0*(0.00146 - 0.00112*(Ch1/Ch0))
    
        if Ch1/Ch0 >= 1.3:
            Lux=0

        return Lux

# Get data from the temperature sensor and return the value in Celsius; trigger the motor (sprinkler)
# if temperature remains high (29 Celsius) for 3 seconds
def temp_sensor():
        global temp_state
        global start
        temp = i2c.readfrom_mem(0x40, 0x01, 2)
        temp1 = int.from_bytes(temp, 'big')
        
        if (temp1 < var):
                temp2 = (temp1 / 4 ) * 0.03125
        elif (temp1 >= var):
                temp2 = (temp1 / 4 - var) * 0.03125
        
        if (temp2 >= 29):
                if(temp_state == 0):
                        temp_state = 1
                        start = time.time()
                elif ( (time.time() - start) > 3 ):
                        motor(1)
                        temp_state = 0
        elif (temp2 < 29):
                temp_state = 0

        return temp2
                
                
# Control the lED output to maintain a steady lighting level   
def light(Lux):
        if(Lux <=25):
                pwm.duty(round(1020-Lux*40))
        else:
                pwm.duty(0)

# Control the motor(sprinkler) by the user so as to control irrigation  
def motor(msg):
        t = int(msg)
        servo.duty(30)
        time.sleep(t)
        servo.duty(122)

# Trigger the motor(sprinkler) every minute
def motor_regular():
        if(rtc.datetime()[6] == 0):
                servo.duty(30)
                time.sleep(1)
                servo.duty(122)

# Callback function: Read input from user to control the device       
def message(topic, msg):
    global state
    # User input: turn off the light
    if msg == b'off':
            state = 0
            print("off")
    # User input: turn on the  light
    elif msg == b'on':
            state = 1
            print("on")
    # User input: Open the water gate, 5 different levels of watering
    elif (msg == b'1' or msg == b'2'or msg == b'3' or msg == b'4' or msg == b'5' ):
            motor(msg)
        
#-----------------------------------------Wi-Fi Connection--------------------------------------#     

ap_if=network.WLAN(network.AP_IF)
ap_if.active(False)
sta_if = network.WLAN(network.STA_IF)
sta_if.active(True)
sta_if.connect('EEERover','exhibition')
time.sleep(5)
# print(sta_if.isconnected())

#----------------------------------------MQTT Connection----------------------------------------#

Clientid = ubinascii.hexlify(machine.unique_id())
client = MQTTClient(Clientid, "192.168.0.10")
client.set_callback(message)
client.connect()
client.subscribe("LED54")

#--------------------------------------------Main Loop------------------------------------------#   

while(1):
    client.check_msg()

    #When users input "on": turn on the device and publish the data to broker
    if(state == 1):
            Lux = lux_sensor()
            light(Lux)
            Temp = temp_sensor()
            motor_regular()
            time_f = str(rtc.datetime()[0]) + "/" + str(rtc.datetime()[1]) + "/" + str(rtc.datetime()[2]) + " " + str(rtc.datetime()[4]) + ":" + str(rtc.datetime()[5]) + ":" + str(rtc.datetime()[6])
            payload = ujson.dumps({"Time":time_f, "Lux":Lux, "Temperature": Temp})
            print(payload)
            client.publish('LED-54', bytes(payload, 'utf-8'))

    #When users input "off": turn off the device elif(state == 0):
    else: pwm.duty(0)
