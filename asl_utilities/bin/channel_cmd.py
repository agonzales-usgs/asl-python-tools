#!/usr/bin/env python
import asl

import asyncore
import Queue
import socket
import struct
import sys
import threading
import time

from jtk import hexdump

class Notifier(asyncore.dispatcher):
    def __init__(self):
        asyncore.dispatcher.__init__(self)
        self.sock_in = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_in.bind(('', 0))
        self.address = ('127.0.0.1', self.sock_in.getsockname()[1])
        self.sock_out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.set_socket(self.sock_in)

    def notify(self):
        print "Sending Nofication..."
        self.sock_out.sendto('CHANGED', self.address)

    def handle_read(self):
        print "Nofication Received."
        msg = self.sock_in.recv(7)
        return len(msg)

    def writable(self):
        return False

class TCPSocket(asyncore.dispatcher):
    def __init__(self, queue):
        asyncore.dispatcher.__init__(self)
        self._connected = False
        self._master_queue = queue
        self._packet_queue = Queue.Queue()
        self._current_packet = ""
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.setblocking(0)

    def handle_connect(self):
        print "Connection Established"
        self._connected = True

    def handle_read(self):
        self._connected = True
        try:
            packet = self.recv(512)
        except socket.error, e:
            print "Socket Error: %s" % str(e)
            return 0
        self._master_queue.put(packet)
        if not packet:
            return 0
        return len(packet)

    def handl_write(self):
        bytes_sent = 0
        try:
            if (self._current_packet == ""): 
                self._current_packet = self._packet_queue.get_nowait()
            bytes_sent = self.send(self._current_packet)
            if (len(bytes_sent) < len(self._current_packet)):
                self._current_packet = self._current_packet[bytes_sent:]
            else:
                self._current_pcaket = ""
        except Queue.Empty:
            return 0
        except socket.error, e:
            print "Socket Error: %s" % str(e)
            return 0
        return len(bytes_sent)

    def handle_close(self):
        print "Connection Closed"
        self._connected = False

    def writable(self):
        if self._current_packet != "":
            return True
        if not self._packet_queue.empty():
            return True
        return False

    def put(self, packet):
        try:
            self._packet_queue.put_nowait(packet)
        except Queue.Full:
            print "Packet Queue is full"

class IOThread(threading.Thread):
    def __init__(self, address):
        threading.Thread.__init__(self, name="IOThread")
        self.address = address
        self.running = False
        self.queue = Queue.Queue()
        self.socket = TCPSocket(self.queue)
        self.notifier = Notifier()

    def run(self):
        self.running = True
        while self.running:
            print "IOThread Loop..."
            if self.socket == None:
                print "Attempting to establish connection to %s:%d" % self.address
                self.socket = TCPSocket(self.queue)
                try:
                    self.socket.connect(self.address)
                except socket.error:
                    print "Could not establish connection."
                    del self.socket
                    self.socket = None
                    time.sleep(0.1)
                    continue

            map = {
                self.notifier.socket : self.notifier,
                self.socket.socket   : self.socket,
            }
            try:
                asyncore.loop(timeout=5.0, use_poll=False, map=map, count=1)
            except socket.error, e:
                print "asyncore.loop() caught an exception: %s" % str(e), 'err'
                # If there is an issue with this socket, we need to create
                # a new socket. Set it to disconnected, and it will be replaced.
                self.socket._connected = False
                time.sleep(0.1)

            if not self.socket._connected:
                try:
                    self.socket.close()
                except:
                    pass
                del self.socket
                self.socket = None
                time.sleep(0.1)

    def notify(self):
        print "Notify requested."
        self.notifier.notify()

    def put(self, message):
        print "Put requested."
        self.socket.put(message)

    def get(self):
        print "Get requested."
        if not self.queue.empty():
            return self.queue.get_nowait()
        return None

    def halt(self):
        print "Halt requested."
        self.running = False
        self.notify()

class Main(object):
    def __init__(self, ip, port):
        self.address = (ip, port)
        self.count = 0
        self.queue = Queue.Queue()
        self.io = IOThread(self.address)

    def start(self):
        self.io.start()
        try:
            msg = ""
            while msg not in (".exit", ".quit"):
                if msg != "":
                    msg_padded = msg.ljust(512, chr(0))
                    raw = struct.pack(">%ds" % len(msg_padded), msg_padded)
                    self.io.put(raw)

                reply = self.io.get()
                while reply is not None:
                    print hexdump.hexdump(reply)
                    reply = self.io.get()

                try:
                    self.count += 1
                    msg = raw_input("%d> " % self.count)
                except EOFError:
                    print
                except KeyboardInterrupt:
                    pass
        except KeyboardInterrupt:
            print
        self.io.halt()
        self.io.join()

if __name__=='__main__':
    import optparse
    parser = optparse.OptionParser()

    parser.add_option(
        '-H','--host',
        dest='ip',default='127.0.0.1',
        help='IP address of TCP server')
    parser.add_option(
        '-p','--port',
        type='int',dest='port',default=7777,
        help='TCP port address of TCP server')
    options, args = parser.parse_args()

    Main(options.ip, options.port).start()

