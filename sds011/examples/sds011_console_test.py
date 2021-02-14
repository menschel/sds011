from sds011 import SDS011
import csv

PORT = "/dev/ttyUSB0"

sds = SDS011(port=PORT, use_database=True)
# sds.set_working_period(rate=5)#one measurment every 5 minutes offers decent granularity and at least a few years of
# lifetime to the sensor
print(sds)

try:
    with open("measurments.csv", "w") as csvfile:
        log = csv.writer(csvfile, delimiter=" ", quotechar="|", quoting=csv.QUOTE_MINIMAL)
        log_columns = ["timestamp", "pm2.5", "pm10", "device_id"]
        log.writerow(log_columns)
        while True:
            measurement = sds.read_measurement()
            values = [str(measurement.get(key)) for key in log_columns]
            log.writerow(values)
            csvfile.flush()
            print(values)


except KeyboardInterrupt:
    sds.__del__()
