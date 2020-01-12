from sds011 import SDS011

port = "/dev/ttyUSB0"

sds = SDS011(port=port,use_database=True)
sds.set_working_period(rate=5)#one measurment every 5 minutes offers decent granularity and at least a few years of lifetime to the sensor
print(sds)
import csv
try:
    with open("measurments.csv","w") as csvfile:
        log = csv.writer(csvfile, delimiter=" ",quotechar="|", quoting=csv.QUOTE_MINIMAL)
        logcols = ["timestamp","pm2.5","pm10","devid"]
        log.writerow(logcols)
        while True:
            meas = sds.read_measurement()
            vals = [str(meas.get(k)) for k in logcols]
            log.writerow(vals)
            print(vals)
            
            
except KeyboardInterrupt:
    sds.sleep()
    sds.__del__()
