#file: databasehandler.py
#author: (C) Patrick Menschel  2018
#purpose: handle the database part of sds011 project
#note: we are using sqlite for convenience as most people don't run a full scale sql server

import sqlite3
# import os

db3path = "measurements.db3"
measurmenttable = "measurements"


class databasehandler():
    
    
    def __init__(self,db3path=db3path):
        self.db3path=db3path
#         if not os.path.exists(db3path):
#             self.init_db()
#         
#     def init_db(self):
#         conn = sqlite3.connect(self.db3path)
#         c = conn.cursor()
#         tables = [i[0] for i in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
#         if measurmenttable not in tables:
#             c.execute("""create table {0} (timestamp datetime , pm2_5 float , pm10 float , devid integer)""".format(measurmenttable))
#         conn.commit()
#         conn.close()
    
    def add_measurement(self,measurement):
        conn = sqlite3.connect(self.db3path)
        c = conn.cursor()
        tables = [i[0] for i in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        if measurmenttable not in tables:
            c.execute("""create table {0} (timestamp datetime , pm2_5 float , pm10 float , devid integer)""".format(measurmenttable))
        linedata = [measurement.get(x) for x in ["timestamp","pm2.5","pm10","devid"]]
        c.execute("insert into {0} (timestamp,pm2_5,pm10,devid) values (?,?,?,?)".format(measurmenttable),linedata)
        conn.commit()
        conn.close()
