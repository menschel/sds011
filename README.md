# sds011

This module is a Python3 based client for the sds011 fine dust (smog) sensor.
The sds011 is a cheap sensor from  [Nova Fitness Co., Ltd.](https://www.inovafitness.com) capable to measure pm2.5 and pm10 particle density in the air.
See the [Spec Sheet](https://cdn.sparkfun.com/assets/parts/1/2/2/7/5/Laser_Dust_Sensor_Control_Protocol_V1.3.pdf) for further info.

## some things to know about the sensor

* It is active fan and takes about 100mA when the fan is running.
* The critical component is the laser diode inside which has a lifetime of a few 1000 hours, so if using the sensor for permanent measurements, it will not last a year. 
  Setting the working period to about 5 minutes is a decent choice for granularity and lifetime.
* The sensor usually comes with a chinese CH341 USB2.0 serial adapter which is not a problem for linux systems but for windows and mac as the drivers sometimes are hard to get.
  In case you're planning to use the sensor on windows, get an FTDI USB to 5V-TTL converter cable.


# basic gui

A PyQt5 APP provides basic sensor information and a plot function.

```
python3 sds011_pyqt5app.pyw
```
or running the script as executable

![SDS011Plot](resources/sds011_plot.png)



## how to use the module

define a serial port usually a "ttyUSB" or a "com" port
```
port = "/dev/ttyUSB0"
```
make an instance of the SDS011 class
```
sds = SDS011(port=port)
```
get some info on the sensor to check if it's working fine
```
print(sds)
```
set a working period for the sensor 
```
sds.set_working_period(rate=5)
```
get a dictionary with the keys "timestamp","pm2.5","pm10","devid" from the measurement queue
```
meas = sds.read_measurement()
```
This is a blocking function, so it waits until a measurement is received from the sensor, which can take some time depending on the working period. 

## getting values by socket

If the module is called with socket option,
```
sds = SDS011(port=port,use_socket=True,socket_portnum=9999)

```
it will open a socket on localhost and the given port which defaults to 9999.
You can check the output via netcat
```
nc localhost 9999
```
which outputs timestamp, pm2.5, pm10, device id
```
2018-06-02 10:36:04.980272,33.5,53.6,43897
2018-06-02 10:41:04.981235,39.5,145.3,43897
2018-06-02 10:54:14.573174,29.5,61.4,43897
```

## database option
If the module is called with database option,
```
sds = SDS011(port=port,use_database=True)
```
it will write values to an sqlite database.
