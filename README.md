# uPurifier
Firmware for ESP8266-based custom PCBs that connects IKEA Air Purifiers to Home Assistant via MQTT

# How it works

Flash the firmware image (see latest release) to ESP8266. Now you can access to the chip via captive portal. On your computer check avaiable networks and choose the one with a name of MicroPython-xxxxxx. Default password is micropythoN.

On the login page choose an air purifier and add your wifi and mqtt credentials. Don't forget to add a Home Assistant (HA) entity id of your choice to your deivce as the example below. After you click on connect, the ESP should reboot and within a few seconds try to establish wireless connection with your router, mqtt broker and HA instance. If it's successful then it automatically publish config entry to Home Assistant to set up your device properties.

![settings](https://user-images.githubusercontent.com/44551566/223481337-2923b91a-d781-4323-ad16-ef498274ddf4.png)

That's all! Now you can see your new fan entity in HA with options to turn on/off or even change speed of the purifier.

# Prerequisites

Home Assistant with Mosquitto MQTT add-on already installed
Förnuftig or Uppatvind Air Purifiers from IKEA
Custom PCB for IKEA Air Purifiers (for more details check esp8266-for-fornuftig and esp8266-for-uppatvind repos)
