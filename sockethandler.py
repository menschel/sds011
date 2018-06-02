#file: sockethandler.py
#author: (C) Patrick Menschel  2018
#purpose: handle the socket communication of sds011 project


import threading
from queue import Queue#,Empty
import socket

class sockethandler():
 
    def __init__(self,port=9999):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.host = "localhost"                           
        self.port = port
        self.sock.bind((self.host, self.port))
        self.sock.listen(5)#up to 5 requests
        self.txqueue = Queue()
        self.listeners = []
        self.connhandler = threading.Thread(target=self.handle_connections)
        self.connhandler.setDaemon(True)
        self.connhandler.start()
        self.pushhandler = threading.Thread(target=self.pushoutmessage)
        self.pushhandler.setDaemon(True)
        self.pushhandler.start()
        #print("init socket handler")
         
 
    def handle_connections(self):
        #print("handles connections")
        while True:
            clientsocket,addr = self.sock.accept()
            self.listeners.append((clientsocket,addr))
     
    def pushoutmessage(self):
        #print("pushing")
        while True:
            outmessage = self.txqueue.get()
            msg = "{0}\n".format(",".join([str(outmessage.get(x)) for x in outmessage.keys()]))
            #print(msg)
            for clientsocket,addr in self.listeners:
                clientsocket.sendall(msg.encode())
             
    def queue_tx_message(self,item):
        return self.txqueue.put(item=item)
      

    def __del__(self):
        #self.sock.shutdown(flag=)
        self.sock.close()