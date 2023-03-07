"""

uPurifier is a firmware for ESP8266-based custom PCBs that connects
IKEA Air Purifiers to Home Assistant via MQTT

(C) Copyright Gergo Horvath @2023.
Released under the GPL v3.0 licence.

Official repos related to this project:
https://github.com/horvathgergo/uPurifier
https://github.com/horvathgergo/esp8266-for-uppatvind
https://github.com/horvathgergo/esp8266-for-fornuftig

"""

import gc
from umqtt.simple import MQTTClient
import socket
import network
from machine import Pin, PWM, reset, unique_id
import ubinascii
import json
import time
import os
gc.collect()


class SmartAirPurifier():
    
    def __init__(self):
        self.client_id = ubinascii.hexlify(unique_id()) 
        self.client_type = os.uname().sysname.upper()
        self.wifi = network.WLAN(network.STA_IF)
        self.wifi.active(True)
        self.ap = network.WLAN(network.AP_IF)
        self.ap.active(False)
        self.device_type = None
        self.config = {}
        self.modes = {
                0: {'state':'OFF', 'speed':  0, 'freq':  1, 'duty':  0, 'preset': 'off'   },
                1: {'state':'ON' , 'speed': 33, 'freq':152, 'duty':512, 'preset': 'low'   },
                2: {'state':'ON' , 'speed': 66, 'freq':225, 'duty':512, 'preset': 'medium'},
                3: {'state':'ON' , 'speed':100, 'freq':300, 'duty':512, 'preset': 'high'  },
                'ON':  {'state':'ON' , 'speed':100, 'freq':300, 'duty':512, 'preset': 'high' },
                'OFF': {'state':'OFF', 'speed':  0, 'freq':  1, 'duty':  0, 'preset': 'off'  },
                'off':    {'state':'OFF', 'speed':  0, 'freq':  1, 'duty':  0, 'preset': 'off'    },
                'low':    {'state':'ON' , 'speed': 33, 'freq':152, 'duty':512, 'preset': 'low'    },
                'medium': {'state':'ON' , 'speed': 66, 'freq':225, 'duty':512, 'preset': 'medium' },
                'high':   {'state':'ON' , 'speed':100, 'freq':300, 'duty':512, 'preset': 'high'   },
                }
                
        
    def configure(self):
        """
        Configure ESP based on device type.
        """
        if self.device_type == 'fornuftig': 
            self.btn3 = Pin(14, Pin.IN, Pin.PULL_UP)
            self.btn2 = Pin(12, Pin.IN, Pin.PULL_UP)
            self.btn1 = Pin(13, Pin.IN, Pin.PULL_UP)
            self.max_freq = 300 #Hz
            self.pwm = PWM(Pin(5, Pin.OUT), freq=1, duty=0)
            self.fg = Pin(4, Pin.IN, Pin.PULL_UP)
            self.url = 'https://github.com/horvathgergo/esp8266-for-fornuftig'
            
        elif self.device_type == 'uppatvind':
            self.btn = Pin(13, Pin.IN, Pin.PULL_UP)
            self.max_freq = 300 #Hz
            self.pwm = PWM(Pin(5, Pin.OUT), freq=1, duty=0)
            self.fg = Pin(4, Pin.IN, Pin.PULL_UP)
            self.url = 'https://github.com/horvathgergo/esp8266-for-uppatvind'
  
              
    def load_config(self):
        """
        Handle (read/parse) configuration settings provided by the user.
        """
        with open('config.json', 'r') as f:
            self.config = json.load(f)
        return self.config
     
     
    def save_config(self):
        """
        Handle (write/dump) configuration settings provided by the user.
        """
        with open('config.json', 'w') as f:
            json.dump(self.config, f)
            
            
    def connect_wifi(self):
        """
        Connect to wifi at boot/reboot.
        If wifi connection fails then activate fallback mechanism.
        """
        try:
            self.config = self.load_config()
            self.wifi.connect(self.config["wifi_ssid"], self.config["wifi_psw"]) 
            if not self.wifi.isconnected():
                    time.sleep(4)
                    if not self.wifi.isconnected():
                        self.open_captive_portal()
            print("wifi connection successful")
        except:
            self.open_captive_portal()
         
         
    def connect_mqtt(self):
        """
        Connect to mqtt at boot/reboot.
        Subscibe to state, speed and preset topics.
        If wifi connection fails then activate fallback mechanism.
        """
        try:
            self.device_type = self.config['purifier']
            bas_t = '/{}/{}/'.format(self.device_type, self.client_id.decode())
            self.mqtt_client = MQTTClient(self.client_id,
                                          self.config['mqtt_broker'],
                                          1883,
                                          self.config['mqtt_user'],
                                          self.config['mqtt_psw'])
            self.mqtt_client.set_callback(self.mqtt_callback) 
            self.mqtt_client.set_last_will(bas_t + 'availability/', 'offline', retain=True)
            self.mqtt_client.connect()
            time.sleep(2)
            self.stat_t          = bas_t + 'state/'
            self.cmd_t           = bas_t + 'set/'
            self.pct_stat_t      = bas_t + 'speed_state/'
            self.pct_cmd_t       = bas_t + 'speed_set/'
            self.pr_mode_stat_t  = bas_t + 'mode_state/'
            self.pr_mode_cmd_t   = bas_t + 'mode_set/'
            self.avty_t          = bas_t + 'availability/'
            self.mqtt_client.subscribe(self.cmd_t)
            self.mqtt_client.subscribe(self.pct_cmd_t)
            self.mqtt_client.subscribe(self.pr_mode_cmd_t)
            
            self.mqtt_client.publish(self.stat_t, str('OFF').encode())
            self.mqtt_client.publish(self.pct_stat_t, str(0).encode())
            self.mqtt_client.publish(self.pr_mode_stat_t, str('off').encode())
            gc.collect()
        except:
            self.open_captive_portal()
            
   
    def connect_ha(self):
        """
        Enable mqtt autodiscovery by sending config entry to Home Assistant at startup.
        """
        self.friendly_name = self.config['entity_id'].replace('_',' ')
        self.friendly_name = self.friendly_name[0].upper() + self.friendly_name[1:]

        ha_config = {
            'name'           : self.friendly_name,
            'uniq_id'        : self.client_id.decode(),
            'obj_id'         : self.config['entity_id'],
            'avty_t'         : self.avty_t,
            'pl_avail'       : 'online',
            'pl_not_avail'   : 'offline',
            'stat_t'		 : self.stat_t,
            'cmd_t'			 : self.cmd_t,
            'pct_stat_t'	 : self.pct_stat_t,
            'pct_cmd_t'		 : self.pct_cmd_t,
            'pr_mode_stat_t' : self.pr_mode_stat_t,
            'pr_mode_cmd_t'	 : self.pr_mode_cmd_t,
            'pr_modes'		 : ['off','low','medium','high'],
            'device': {
                'ids'   : [self.device_type, self.client_id.decode()],
                'mf'    : '@horvathgergo',
                'model' : self.device_type[0].upper() + self.device_type[1:] + ' with ' + self.client_type,
                'name'  : 'Purifiers with ' + self.client_type,
                'sw'    : 'v0.1.0-beta',
                'cu'    : self.url,
                }
            
        }
        payload = json.dumps(ha_config)
        discovery_topic = 'homeassistant/fan/'+ self.client_id.decode() + '/config'
        self.mqtt_client.publish(discovery_topic, payload)
        self.mqtt_client.publish(self.avty_t, 'online', retain=True)           
        gc.collect()   
           
           
    def parse_request(self, request):
        """
        Parse HTTP GET request string submitted through the captive portal.
        """
        request = request.split(' ')[1]
        request_params = request[2:].split('&')
        for param in request_params:
            key, value = param.split('=')
            self.config[key] = value
        return self.config


    def css(self):
        """
        Return pre-defined css style for captivel portal.
        """
        with open('style.css', 'r') as f:
            css = f.read()
        return css


    def html(self):
        """
        Return pre-defined structure for captivel portal.
        """
        with open('index.html', 'r') as f:
            html = f.read()
            html = html.replace('{{ css }}', self.css())
            html = html.replace('{{ client_type }}', self.client_type)
            html = html.replace('{{ client_id }}', self.client_id.decode())
            html = html.encode()
        return html


    def open_captive_portal(self):
        """
        Activate captive portal to be able to set or override wifi/mqtt settings.
        """
        self.ap.active(False)
        self.ap.active(True)     
        cp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        gc.collect()
        try:
            cp.bind(('', 80))
        except:
            cp.bind(('192.168.4.2', 80)) 
        cp.listen(5)
        while True:
            conn, addr = cp.accept() 
            request = conn.recv(1024)
            request = request.decode().split('\n',1)[0]
            if '?' in request:
                self.config = self.parse_request(request)
                self.save_config()
                conn.close()
                cp.close()
                self.ap.active(False)
                del request, conn, addr, cp
                gc.collect()
                break
            conn.send('HTTP/1.1 200 OK\r\n')
            conn.send('Content-Type: text/html\r\n')
            conn.send('Connection: close\r\n\r\n')
            conn.sendall(self.html())
            conn.close()
            gc.collect()
        reset()
        
        
    def mqtt_callback(self, topic, msg):
        """
        Handle mqtt callback. Activated when message received on any subscribed topics.
        It evaluates if the msg is valid or not and processes/discards it accordingly.
        Doesn't care too much with the topic :)
        """
        msg = msg.decode()
        try:
            msg = int(msg)
        except:
            pass
        if msg in list(self.modes.keys()) or (0 <= msg <= 100):
            topic = topic.decode()
            try:
                if topic == self.pct_cmd_t:
                    if msg > 66:
                        preset = 3
                    elif msg > 33:
                        preset = 2
                    elif msg > 0:
                        preset = 1
                    else:
                        preset = 0            
                             
                    if msg > 0:
                        self.pwm.freq(min(int(round(float(msg)*2.2+80)), self.max_freq))
                        self.pwm.duty(512)
                        self.mqtt_client.publish(self.stat_t, 'ON')
                        self.mqtt_client.publish(self.pr_mode_stat_t, str(self.modes[preset]['preset']).encode())

                    else:
                        self.pwm.freq(1)
                        self.pwm.duty(0)
                        self.mqtt_client.publish(self.stat_t, 'OFF')
                        self.mqtt_client.publish(self.pr_mode_stat_t, str(self.modes[preset]['preset']).encode())
                    self.mqtt_client.publish(self.pct_stat_t, str(msg).encode())
                else:
                    self.pwm.freq(self.modes[msg]['freq'])
                    self.pwm.duty(self.modes[msg]['duty'])
                    self.mqtt_client.publish(self.stat_t, str(self.modes[msg]['state']).encode())
                    self.mqtt_client.publish(self.pct_stat_t, str(self.modes[msg]['speed']).encode())
                    self.mqtt_client.publish(self.pr_mode_stat_t, str(self.modes[msg]['preset']).encode())
            except:
                pass
        gc.collect()


    def btn_callback(self, btn_state):
        """
        Handle mqtt callback. Activated when button is pressed.
        """
        self.pwm.freq(self.modes[btn_state]['freq'])
        self.pwm.duty(self.modes[btn_state]['duty'])
        self.mqtt_client.publish(self.stat_t, str(self.modes[btn_state]['state']).encode())
        self.mqtt_client.publish(self.pct_stat_t, str(self.modes[btn_state]['speed']).encode())
        self.mqtt_client.publish(self.pr_mode_stat_t, str(self.modes[btn_state]['preset']).encode())


    def main(self, btn_state=0, btn_prev=0, attempts=5):
        """
        This is the main (syncronous) function that check periodically...
        ...physical switch/button actions and mqtt msg on subscribed topics.
        When valid cmd is received it activates callback functions.
        """
        while True:
            try:
                self.mqtt_client.check_msg()
            except:
                if attempts:
                     self.mqtt_client.connect(False)
                     attempts -= 1
                else:
                    pass
            
            if self.device_type == 'fornuftig':
                if not self.btn1.value():
                    btn_state = 1
                elif not self.btn2.value():
                    btn_state = 2
                elif not self.btn3.value():
                    btn_state = 3
                else:
                    btn_state = 0
                if btn_prev != btn_state:
                    print("state: " + str(btn_state))
                    self.btn_callback(btn_state)
                    btn_prev = btn_state
                    
            elif self.device_type == 'uppatvind':
                if not self.btn.value():
                    btn_state = (btn_state + 1) % 4
                    print("state: " + str(btn_state))
                    self.btn_callback(btn_state)
            time.sleep(0.5)

# Run          
purifier = SmartAirPurifier()
purifier.connect_wifi()
purifier.connect_mqtt()
purifier.configure()
purifier.connect_ha()
purifier.main()

