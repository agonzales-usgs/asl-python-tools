#!/usr/bin/env python
try: 
    import asl
    ASL=True
except: 
    """This is just for flash, not essential"""
    ASL=False

import asyncore
import base64
import calendar
import inspect
import optparse
import os
import pprint
import Queue
import re
import socket
import struct
import sys
import threading
import time

HAS_GUI=True
try:
    import pygtk
    pygtk.require('2.0')
    import gtk
    import gobject
    gobject.threads_init()
except:
    HAS_GUI=False
    pass

"""
TCP Forwarding:

(NOTE: Most of this has been done, but there are still
       some bugs to work out.)

We need a way for a TCP connection status to be recognized
both on local and remote pipes. The best way to start is
to add support for local pipes to recognize TCP connections.
Connect, Accept, Write, Read, Close
Each operation must be handled by the MultiPipe class.
Once the MultiPipe knows how to handle these operations, we
must extend the INTERNAL TCP messages to include each of
these operations as well.

Currently we only have one command, 'FWD_DATA'

This must be expanded to handle any number of directives.
For TCP this should include:

'CONNECT' (Host -> Pipe: creates a new TCP Pipe)
'ACCEPT'  (Pipe -> Host: confirms a new TCP Pipe)
'CLOSE'   (either direction: deletes a TCP Pipe)

"""

# === Exceptions /*{{{*/
class ExServerDied(Exception):
    pass
#/*}}}*/

# === Counter Class /*{{{*/
# A simple counter class that keeps track of state (not thread safe)
class Counter(object):
    def __init__(self, value=0, stride=1):
        self.stride = stride
        self.original = value
        self.lock = threading.Lock()
        self.reset()

    def reset_t(self): self.lock.acquire(); self.reset(); self.lock.release()
    def reset(self):
        self.value = self.original

    def set_value_t(self, value): self.lock.acquire(); self.set_value(); self.lock.release()
    def set_value(self, value):
        self.value = value

    def set_stride_t(self, value): self.lock.acquire(); self.set_stride(); self.lock.release()
    def set_stride(self, stride):
        self.stride = stride

    # Post increment
    def inc_t(self, value): self.lock.acquire(); self.inc(); self.lock.release()
    def inc(self):
        self.value += self.stride
        return self.value

    # Post decrement
    def dec_t(self, value): self.lock.acquire(); self.dec(); self.lock.release()
    def dec(self):
        self.value -= self.stride
        return self.value

    # Pre increment
    def inc_p_t(self, value): self.lock.acquire(); self.inc_p(); self.lock.release()
    def inc_p(self):
        temp = self.value
        self.value += self.stride
        return temp

    # Pre decrement
    def dec_p_t(self, value): self.lock.acquire(); self.dec_p(); self.lock.release()
    def dec_p(self):
        temp = self.value
        self.value -= self.stride
        return temp
#/*}}}*/

# === Pipe Classes /*{{{*/
# Base class for all network communications classes which are
# attached to asyncore
class PipeBase(asyncore.dispatcher):
    def __init__(self, master=None):
        asyncore.dispatcher.__init__(self)
        self._hostname      = None  # Remote host name
        self._address       = None  # Remote host (IP,Port)
        self._socket_type   = None  # Connection type (UDP/TCP)

        self._buffers       = []    # Queued write data for this PipeBase object
        self._write_buffer  = ''    # Write buffer which is currently being processed
        self._write_address = None  # Address associated with the current write buffer

        self._rx_packets    = 0     # Number of packets received
        self._rx_bytes      = 0     # Number of bytes received
        self._tx_packets    = 0     # Number of packets sent
        self._tx_bytes      = 0     # Number of bytes sent

        # TCP Connections Only
        self._remote_key    = None  # Key for the remote host format "xxx.xxx.xxx.xxx-ppppp-TCP"
        self._connecting    = False # True when the connection is being initialized
        self._connected     = False # True when the connection has been established
        self._disconnecting = False # True when a request has been made to close the connection

        self._master = master # MultiPipe class instance that "owns" this Pipe component

    def log(self, string, verbosity=1):
        if self._master:
            self._master.log(string, verbosity)

    def set_address(self, address):
        if type(address) is not tuple:
            raise TypeError("address must be of type 'tuple'")
        if len(address) != 2:
            raise TypeError("address must be a tuple of length 2")
        ip, port = address
        if type(ip) is not str:
            raise TypeError("address' first item must be of type 'str'")
        if type(port) is not int:
            raise TypeError("address' second item must be of type 'int'")
        host, port = address
        try:
            ip = socket.gethostbyname(host)
        except socket.gaierror:
            raise ValueError("unknown host")
        self._hostname = host
        self._address = (ip, port)

    def set_socket_type(self, socket_type):
        if type(socket_type) not in (int, str):
            raise TypeError("socket_type must be of type 'str' or 'int'")
        if socket_type not in ('UDP', 'TCP', socket.SOCK_DGRAM, socket.SOCK_STREAM):
            raise ValueError("invalid value for socket_type")
        if type(socket_type) is int:
            self._socket_type = socket_type
        else:
            if socket_type == 'UDP':
                self._socket_type = socket.SOCK_DGRAM
            elif socket_type == 'TCP':
                self._socket_type = socket.SOCK_STREAM

    def get_socket_type(self):
        return self._socket_type

    def get_socket_type_str(self):
        type = self._socket_type
        if self._socket_type == socket.SOCK_DGRAM:
            return 'UDP'
        elif self._socket_type == socket.SOCK_STREAM:
            return 'TCP'
        return ''

    def get_address(self):
        return self._address

    def get_key(self):
        if self._address and self._socket_type:
            return "%s-%d-%s" % (self._address[0], self._address[1], self.get_socket_type_str())
        return ""

    # Add packet to buffer list for transmission
    def queue_packet(self, packet, address=None):
        self.log("Queueing Packet: %s %s" % (str(packet), str(address)), 4)
        if not packet:
            packet = ''
        self._buffers.append((packet, address))

    # Check that there is data queued for writing
    # (Overrides the method in asyncore.dispatcher)
    def writable(self):
        self.log("%s buffers %s" % (self.__class__.__name__, str(self._buffers)), 5)
        self.log("%s write_buffer %s" % (self.__class__.__name__, str(self._write_buffer)), 5)
        self.log("%s write_address %s" % (self.__class__.__name__, str(self._write_address)), 5)
        return (len(self._buffers) > 0) or (len(self._write_buffer) > 0)

    # Check that we are connected before reading
    # (Overrides the method in asyncore.dispatcher)
    def readable(self):
        if self._socket_type == socket.SOCK_STREAM:
            if self._connecting and not self._connected:
                return False
        return True

    # Call the underlying write handler, track the byte and packet counts
    # (Overrides the method in asyncore.dispatcher)
    def handle_write(self):
        self.log("In write handler for %s %s" % (self.__class__.__name__, str(self.get_key())), 4)
        self.log("remote_key   : %s" % str(self._remote_key), 5)
        self.log("connecting   : %s" % str(self._connecting), 5)
        self.log("connected    : %s" % str(self._connected), 5)
        self.log("disconnecting: %s" % str(self._disconnecting), 5)
        if not self._ensure_connected():
            return
        bytes_written = self._handle_write()
        self._last_activity = calendar.timegm(time.gmtime())
        if bytes_written > 0:
            self._tx_bytes   += bytes_written
            self._tx_packets += 1

    def _handle_write(self):
        bytes_written = 0
        self.log("Entered %s::_handle_write" % self.__class__.__name__, 4)
        if (not len(self._write_buffer)) and len(self._buffers):
            self._write_buffer, self._write_address = self._buffers.pop(0)
        if len(self._write_buffer):
            self.log("writing to address %s" % str(self._write_address), 5)
            if self._socket_type == socket.SOCK_STREAM or self._write_address is None:
                bytes_written = self.send(self._write_buffer)
            else:
                bytes_written = self.sendto(self._write_buffer, self._write_address)
            self._write_buffer = self._write_buffer[bytes_written:]
        self.handle_disconnect()
        return bytes_written

    # Call the underlying read handler, track the byte and packet counts
    # (Overrides the method in asyncore.dispatcher)
    def handle_read(self):
        self.log("In read handler for %s %s" % (self.__class__.__name__, str(self.get_key())), 4)
        self.log("remote_key   : %s" % str(self._remote_key), 5)
        self.log("connecting   : %s" % str(self._connecting), 5)
        self.log("connected    : %s" % str(self._connected), 5)
        self.log("disconnecting: %s" % str(self._disconnecting), 5)
        if not self._ensure_connected():
            if not self._connecting:
                self.handle_connect()
        else:
            bytes_read = self._handle_read()
            self._last_activity = calendar.timegm(time.gmtime())
            if bytes_read > 0:
                self._tx_bytes   += bytes_read
                self._tx_packets += 1

    def _ensure_connected(self):
        self.log("%s::_ensure_connected()" % self.__class__.__name__, 4)
        self.log("  connecting = %s" % self._connecting, 5)
        self.log("  connected  = %s" % self._connected, 5)
        #pprint.pprint(inspect.stack())
        if self._socket_type == socket.SOCK_STREAM:
            if not self._connected:
                return False
        return True

    def begin_disconnect(self):
        self._connecting = False
        self._disconnecting = True
        self.handle_disconnect()

    def handle_disconnect(self):
        if self._socket_type == socket.SOCK_STREAM and self._disconnecting and not self.writable():
            self._handle_close()


# Hosts send/receive as if they were the actual host.
# They communicate directly with the initializing client.
class Host(PipeBase):
    def __init__(self, master, address, socket_type='UDP', local_port=None):
        PipeBase.__init__(self, master)
        self._original_socket = None # Socket on which the Host listens for TCP connections

        self.set_address(address)
        self.set_socket_type(socket_type)
        self._original_socket = socket.socket(socket.AF_INET, self.get_socket_type())
        self.set_socket(self._original_socket)
        self.set_reuse_addr()
        try:
            lport = int(local_port)
            self.bind(('', lport))
        except:
            self.bind(('', 0))
        if self._socket_type == socket.SOCK_STREAM:
            self._original_socket.listen(5)

    def _handle_read(self):
        self.log("Host::_handle_read()", 4)
        if not self._ensure_connected():
            self.log("Host::_handle_read() not connected", 2)
            return 0
        packet,address = self.recvfrom(4096)
        if address is None and self._socket_type == socket.SOCK_STREAM:
            client_key = self._remote_key
        else:
            ip,port = address
            client_key = "%s-%d-%s" % (ip, port, self.get_socket_type_str())
        if len(packet) > 0:
            self._master.client_to_host('FWD_DATA', client_key, self.get_key(), packet)
        elif self._socket_type == socket.SOCK_STREAM:
            self.handle_close()
        return len(packet)

    def handle_connect(self):
        self.log("Host::handle_connect()", 3)
        if self._socket_type == socket.SOCK_STREAM:
            if self._connected:
                self.log("Host::handle_connect() already connected", 2)
                return
            if self._connecting:
                self.log("Host::handle_connect() is in the process of connecting", 2)
                return
            new_sock,address = self._original_socket.accept()
            self.log("New connection from: %s" % str(address), 1)
            self.log("Old Socket: %s" % str(self._original_socket), 1)
            self.log("New Socket: %s" % str(new_sock), 1)
            ip,port = address
            client_key = "%s-%d-%s" % (ip, port, self.get_socket_type_str())
            self._remote_key = client_key
            self._connecting = True
            self.set_socket(new_sock)
            self._master.client_to_host('CONNECT', self._remote_key, self.get_key(), 'CONNECT')
            self._master.notify()

    # Each port can only handle a single open connection,
    # so we have to be certain of our state.
    def _handle_accept(self, client_key):
        if self._connected:
            return
        # If we are in the process of disconnection,
        # we are not yet ready for a new connection
        if self._disconnecting:
            return
        # If a connection has not been initialized,
        # we are not ready to accept
        if not self._connecting:
            return
        # If the remote key was not generated for some reason,
        # we cannot establish a connection
        if self._remote_key is None:
            return
        if client_key == self._remote_key:
            self._connected = True
            self._connecting = False

    def handle_close(self):
        self.log("Host::handle_close()", 3)
        #self._connected_to = None
        if self._socket_type == socket.SOCK_STREAM:
            if not self._connected:
                self.log("Host::handle_close() not connected", 2)
                return
            self._master.client_to_host('CLOSE', self._remote_key, self.get_key(), 'CLOSE')
            self._handle_close()
            # Wake up asyncore so it can update file descriptors
            self._master.notify()

    def _handle_close(self):
        self.close()
        self._remote_key = None
        self._connecting = False
        self._connected = False
        self._disconnecting = False
        self.set_socket(self._original_socket)
        self._original_socket.listen(5)


# Pipes send/receive as if they were the actual client.
# They communicate directly with the target host.
class Pipe(PipeBase):
    def __init__(self, master, address, host_key, socket_type='UDP'):
        PipeBase.__init__(self, master)
        self._last_activity = calendar.timegm(time.gmtime())
        self._original_socket = None # Just keeping with convention.

        self._remote_key = host_key # Unique identifier for this pipe's remote connection.
        self.set_address(address)
        self.set_socket_type(socket_type)
        self._original_socket = socket.socket(socket.AF_INET, self.get_socket_type())
        self.set_socket(self._original_socket)
        self.bind(('', 0))

    def _handle_read(self):
        self.log("Pipe::_handle_read()", 4)
        self.log("self._connected = %s" % str(self._connected), 5)
        packet,address = self.recvfrom(4096)
        self.log("packet size: %d" % len(packet), 5)
        if len(packet) > 0:
            self._master.host_to_client('FWD_DATA', self._remote_key, self.get_key(), packet)
        elif self._socket_type == socket.SOCK_STREAM:
            self.handle_close() # If we received an empty string from at TCP connection, the client closed their socket
        return len(packet)

    def handle_connect(self):
        self.log("Pipe::handle_connect()", 3)
        if self._socket_type == socket.SOCK_STREAM:
            self._master.host_to_client('ACCEPT', self._remote_key, self.get_key(), 'ACCEPT')
            self._connected = True

    # The Client class always initiates connections with the real host
    # I think I just added this to see if this was being called...
    def handle_accept(self):
        self.log("Pipe::handle_accept()", 3)

    def handle_close(self):
        self.log("Pipe::handle_close()", 3)
        if self._socket_type == socket.SOCK_STREAM:
            self._master.host_to_client('CLOSE', self._remote_key, self.get_key(), 'CLOSE')
            self._handle_close()
            # Wake up asyncore so it can update file descriptors
            self._master.notify()

    def _handle_close(self):
        self.close()
        self._remote_key = None
        self._connecting = False
        self._connected = False
        self._disconnecting = False
        self._master.del_pipe(self.get_key())

# Writes to itself to force asyncore to re-evaluated file descriptors
# This is necessary both when adding and removing pipes
# - A new pipe needs to be added to asyncore's file descriptor list
# - An old pipe should not be left in the list, or we may receive a
#   response that we are unable to handle. This may actually be an
#   issue still, as we do not tend to destroy the Client/Host after the
#   notification is done...
class Notifier(PipeBase):
    def __init__(self, master):
        PipeBase.__init__(self, master)
        self.sock_in = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_in.bind(('', 0))
        self.set_address(('127.0.0.1', self.sock_in.getsockname()[1]))
        self.sock_out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.set_socket(self.sock_in)

    def notify(self):
        self.log("-=NOTIFIER=-", 2)
        self.sock_out.sendto('CHANGED', self.get_address())

    def _handle_read(self):
        msg = self.sock_in.recv(7)
        return len(msg)

    def writable(self):
        return False


# Base class for TCP communication between upipe instances
class Internal(PipeBase):
    def __init__(self, master):
        PipeBase.__init__(self, master)
        self.r_cmd  = "[A-Za-z0-9_]+" # Command character set regex
        self.r_ip   = "(?:\d{1,3})[.](?:\d{1,3})[.](?:\d{1,3})[.](?:\d{1,3})" # IP address regex
        self.r_key  = "%s[-]\d+[-][a-zA-Z]+" % self.r_ip # key regex
        self.r_data = "[0-9A-Za-z+-_/=]+" # Data character set regex (base-64 encoded)
        self.regex_message = re.compile("^<\[(%s)\]\((%s)\)\((%s)\)\{(%s)\}>$" % (self.r_cmd, self.r_key, self.r_key, self.r_data))

    def _handle_read(self):
        msg = self.recv(4096)
        self.log("%s::_handle_read()  msg: %s" % (self.__class__.__name__, msg), 5)
        pot = self.melt(msg)
        if pot is None:
            return len(msg)
        command, src_key, dst_key, packet = pot
        self._src_to_dst(command, src_key, dst_key, packet)
        return len(msg)

    # Break down a message into keys and data
    def melt(self, message):
        self.log("Melting: %s" % str(message), 1)
        match = self.regex_message.search(message)
        if match:
            groups = match.groups()
            command = groups[0]
            src_key = groups[1]
            dst_key = groups[2]
            packet  = base64.standard_b64decode(groups[3])
            self.log("Melt Succeeded!", 3)
            return (command, src_key, dst_key, packet)
        self.log("Melt Failed!", 3)
        return None

    # Assemble a message from keys and data
    def freeze(self, src_key, dst_key, packet, command='FWD_DATA'):
        message = "<[%s](%s)(%s){%s}>" % (command, src_key, dst_key, base64.standard_b64encode(packet))
        self.log("Freezing: %s" % str(message), 1)
        match = self.regex_message.search(message)
        if match:
            self.log("Freeze Succeeded!", 3)
            return message
        self.log("Freeze Failed!", 3)
        return None


# Client host comm. handler
class InternalHosts(Internal):
    def __init__(self, master, address):
        Internal.__init__(self, master)

        #sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #sock.bind(('', 0))
        #self.set_socket(sock)
        #sock.connect(address)
        #sock.send('Greetings Server')
        #self.log("Client is connected on ('%s', %d)" % sock.getsockname(), 3)

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.bind(('', 0))
        self._socket.connect(address)
        self.set_socket(self._socket)
        #self._socket.send('Greetings Server')
        self.log("Client is connected on ('%s', %d)" % self._socket.getsockname(), 3)

    def handle_connect(self):
        pass
        #self.set_socket(self._socket.accept()[0])

    def handle_close(self):
        raise ExServerDied("The Client Server Died")
        #self.set_socket(None)

    def _src_to_dst(self, command, host_key, client_key, packet):
        self.log("InternalHosts::_src_to_dst()", 4)
        self._master.host_to_client(command, host_key, client_key, packet)


# Server client comm. handler
class InternalClients(Internal):
    def __init__(self, master, address):
        Internal.__init__(self, master)
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._socket.bind(address)
        except:
            self._socket.bind(('', 0))
        self.log("Server is running at ('%s', %d)" % self._socket.getsockname(), 0)
        self.set_socket(self._socket)
        self._socket.listen(1)

    def handle_connect(self):
        self.set_socket(self._socket.accept()[0])
        self.log("Client connection accepted", 0)

    def handle_close(self):
        self._master._remove_all_pipes()
        self.handle_connect()

    def _src_to_dst(self, command, client_key, host_key, packet):
        self.log("InternalClients::_src_to_dst()", 4)
        self._master.client_to_host(command, client_key, host_key, packet)
#/*}}}*/

# === Core Classes /*{{{*/
# Base class for pipe management
class MultiPipe(threading.Thread):
    def __init__(self, log=False, verbosity=0):
        threading.Thread.__init__(self)
        self._sockets = {}
        self._sockets['NOTIFIER'] = Notifier(self)
        self._running = False
        self._pipe_timeout = 300 #seconds
        self._log = log == True
        self._verbosity = verbosity
        self._local = True

    def log(self, string, verbosity=1):
        if verbosity <= self._verbosity:
            print string

    def run(self):
        self._running = True
        while self._running:
            self._clean()
            self.log("MAP:", 6)
            self.log(str(self._sockets), 6)
            self.log(str(self._get_map()), 6)
            asyncore.loop(30.0, False, self._get_map(), 1)
        self._remove_all_pipes()

        try: self._scokets['INTERNAL'].close() 
        except: pass
        try: del self._sockets['INTERNAL']
        except: pass

        try: self._sockets['NOTIFIER'].close()
        except: pass
        del self._sockets['NOTIFIER']

    def notify(self):
        self._sockets['NOTIFIER'].notify()

    def add_host(self, address, socket_type='UDP', local_port=None):
        host = Host(self, address, socket_type, local_port)
        if not self._sockets.has_key(host.get_key()):
            self._sockets[host.get_key()] = host
            self.log("New Host: %s" % str(host.socket.getsockname()), 0)
            self.notify()

    def del_host(self, key):
        if self._sockets.has_key(key): 
            if self._sockets[key].__class__.__name__ == 'Host':
                del self._sockets[key]
                self.notify()
    
    def del_pipe(self, key):
        if self._sockets.has_key(key):
            if self._sockets[key].__class__.__name__ == 'Pipe':
                del self._sockets[key]
                self.notify()

    def stop(self):
        self._running = False
        self.notify()

    def _get_map(self):
        map = {}
        for k,s in self._sockets.items():
            map[s.socket] = s
        self.log("%s::_get_map" % (self.__class__.__name__,), 7)
        self.log(str(map), 7)
        self.log(str(self._sockets), 7)
        return map

    def _clean(self):
        now = calendar.timegm(time.gmtime())
        for k,v in self._sockets.items():
            if v.__class__.__name__ == 'Pipe':
                if (not v._socket_type == socket.SOCK_STREAM) or (not v._connected):
                    if not self._sockets.has_key(v._remote_key):
                        self.log("retiring client '%s' with no associated host" % k, 1)
                        del self._sockets[k]
                    elif (now - v._last_activity) > self._pipe_timeout:
                        self.log("retiring old client '%s'" % k, 1)
                        del self._sockets[k]

    def _remove_all_pipes(self):
        for k,v in self._sockets.items():
            if k not in ('NOTIFIER', 'INTERNAL'):
                del self._sockets[k]

    def host_to_client(self, command, host_key, client_key, packet):
        self.log("%s::host_to_client():" % (self.__class__.__name__,), 1)
        self.log("    host   : %s" % str(host_key), 1)
        self.log("    client : %s" % str(client_key), 1)
        self.log("    command: %s" % str(command), 1)
        self.log("    # bytes: %d" % len(packet), 1)
        self.log("", 1)

        h_ip,h_port,h_type = host_key.split('-',2)
        c_ip,c_port,c_type = client_key.split('-',2)
        if h_type != c_type:
            self.log("%s::client_to_host(): mismatch between client '%s' and host '%s' connection type" % (self.__class__.__name__, client_key, host_key), 0)
            return
        h_address = (h_ip,int(h_port))
        c_address = (c_ip,int(c_port))
        type = c_type

        if command == 'CLOSE':
            if not self._sockets.has_key(host_key):
                self.log("%s::host_to_client(): recieved 'CLOSE' command for invalid host key (%s)" % (self.__class__.__name__, host_key), 0)
                return
            host = self._sockets[host_key]
            host.begin_disconnect()
        elif command == 'ACCEPT':
            if not self._sockets.has_key(host_key):
                self.log("%s::host_to_client(): recieved 'ACCEPT' command for invalid host key (%s)" % (self.__class__.__name__, host_key), 0)
                return
            host = self._sockets[host_key]
            if host._connected:
                self.log("%s::host_to_client(): recieved 'ACCEPT' command for host key (%s), but we are already connected to host key (%s)" % (self.__class__.__name__, host_key, self._remote_key), 0)
                return
            self.log("host_to_client():", 2)
            self.log("Host: %s" % str(host), 2)
            self.log("remote key: %s" % str(host._remote_key), 2)
            self.log("connecting: %s" % str(host._connecting), 2)
            self.log("connected : %s" % str(host._connected), 2)
            host._handle_accept(client_key)
        elif command == 'FWD_DATA':
            if self._local and not self._sockets.has_key(client_key):
                self.log("%s::host_to_client(): recieved 'FWD_DATA' command with invalid client key (%s)" % (self.__class__.__name__, client_key), 0)
                return
            if not self._sockets.has_key(host_key):
                self.log("%s::host_to_client(): recieved 'FWD_DATA' command with invalid host key (%s)" % (self.__class__.__name__, host_key), 0)
                return
            host   = self._sockets[host_key]
            self.log("MultiPipe::host_to_client(): adding packet", 3)
            self.log("    host   : %s" % str(host_key), 3)
            self.log("    client : %s" % str(client_key), 3)
            self.log("", 3)
            self.log_packet(host_key, client_key, packet)
            host.queue_packet(packet, c_address)

    def client_to_host(self, command, client_key, host_key, packet):
        self.log("%s::client_to_host():" % self.__class__.__name__, 1)
        self.log("    client : %s" % str(client_key), 1)
        self.log("    host   : %s" % str(host_key), 1)
        self.log("    command: %s" % str(command), 1)
        self.log("    # bytes: %d" % len(packet), 1)
        self.log("", 1)

        if self._local: 
            if not self._sockets.has_key(host_key):
                return
        h_ip,h_port,h_type = host_key.split('-',2)
        c_ip,c_port,c_type = client_key.split('-',2)
        if h_type != c_type:
            self.log("%s::client_to_host(): mismatch between client '%s' and host '%s' connection type" % (self.__class__.__name__, client_key, host_key), 0)
            return
        h_address = (h_ip,int(h_port))
        c_address = (c_ip,int(c_port))
        type = c_type

        if command == 'CLOSE':
            if not self._sockets.has_key(client_key):
                return
            client = self._sockets[client_key]
            client.begin_disconnect()
        elif command == 'CONNECT':
            if not self._sockets.has_key(client_key):
                client = Pipe(self, c_address, host_key, type)
                self._sockets[client.get_key()] = client
                client.connect(h_address)
            else:
                self.log("Client Key '%s' already exists" % client_key, 0)
        elif command == 'FWD_DATA':
            if not self._sockets.has_key(client_key):
                if type == 'TCP':
                    self.log("%s::client_to_host(): received command 'FWD_DATA' for invalid client key (%s)" % (self.__class__.__name__, client_key), 0)
                    return
                client = Pipe(self, c_address, host_key, type)
                self._sockets[client.get_key()] = client
            else:
                client = self._sockets[client_key]
            self.log_packet(client_key, host_key, packet)
            client.queue_packet(packet, h_address)

    def log_packet(self, source_key, destination_key, packet):
        if self._log:
            print "TRAFFIC FROM[%s] TO[%s] BYTES[%s] TIME[%s]" % (source_key, destination_key, len(packet), time.strftime("%Y-%m-%d (%j) %H:%M:%S", time.gmtime()))

# Base class for multi-host pipe server/client
class MultiPipeTCP(MultiPipe):
    def __init__(self, log=False, verbosity=0):
        MultiPipe.__init__(self, log=log, verbosity=verbosity)
        self._local = False

    def src_to_dst(self, command, src_key, dst_key, packet):
        message = self._sockets['INTERNAL'].freeze(src_key, dst_key, packet, command)
        self.log_packet(src_key, dst_key, packet)
        self._sockets['INTERNAL'].queue_packet(message)

    def _clean(self):
        now = calendar.timegm(time.gmtime())
        for k,v in self._sockets.items():
            if v.__class__.__name__ == 'Pipe':
                if (not v._socket_type == socket.SOCK_STREAM) or (not v._connected):
                    if (now - v._last_activity) > self._pipe_timeout:
                        self.log("retiring old client '%s'" % k, 1)
                        del self._sockets[k]


# Client pipe manager
class MultiPipeHosts(MultiPipeTCP):
    def __init__(self, address, log=False, verbosity=0):
        MultiPipeTCP.__init__(self, log=log, verbosity=verbosity)
        self._sockets['INTERNAL'] = InternalHosts(self, address)

    # Override the client_to_host() method so that packets
    # are forwarded over the TCP link rather than attempting
    # to send directly to the host.
    def client_to_host(self, command, client_key, host_key, packet):
        self.src_to_dst(command, client_key, host_key, packet)


# Server pipe manager
class MultiPipeClients(MultiPipeTCP):
    def __init__(self, address, log=False, verbosity=0):
        MultiPipeTCP.__init__(self, log=log, verbosity=verbosity)
        self._sockets['INTERNAL'] = InternalClients(self, address)

    # Override the host_to_client() method so that packets
    # are forwarded over the TCP link rather than attempting
    # to send directly to the client.
    def host_to_client(self, command, host_key, client_key, packet):
        self.src_to_dst(command, host_key, client_key, packet)
#/*}}}*/

# === User Interface /*{{{*/
class PipeUI:
    def __init__(self, local=True, log=False, verbosity=0):
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title("Multi-Pipe")
        if ASL:
            self.window.set_icon(asl.new_icon('upipe'))

# ===== Widget Creation ===========================================
        self.vbox_main    = gtk.VBox()
        self.vbox_hosts   = gtk.VBox()
        self.hbox_new     = gtk.HBox()
        self.hbox_control = gtk.HBox()

        #self.table_hosts = gtk.Table()
        self.hosts = {}

      # User Interaction Widgets
        self.entry_lport   = gtk.Entry()
        self.label_sep1    = gtk.Label(":")
        self.entry_ip      = gtk.Entry()
        self.label_sep2    = gtk.Label(":")
        self.entry_port    = gtk.Entry()
        self.combobox_type = gtk.combo_box_new_text()
        self.button_add    = gtk.Button(stock=gtk.STOCK_ADD)

        self.button_add = gtk.Button(stock=None)
        self.hbox_add   = gtk.HBox()
        self.image_add  = gtk.Image()
        self.image_add.set_from_stock(gtk.STOCK_ADD, gtk.ICON_SIZE_MENU)
        self.label_add  = gtk.Label('Add')
        self.button_add.add(self.hbox_add)
        self.hbox_add.pack_start(self.image_add, padding=1)
        self.hbox_add.pack_start(self.label_add, padding=1)

        self.button_quit = gtk.Button(stock=None)
        self.hbox_quit   = gtk.HBox()
        self.image_quit  = gtk.Image()
        self.image_quit.set_from_stock(gtk.STOCK_QUIT, gtk.ICON_SIZE_MENU)
        self.label_quit  = gtk.Label('Quit')
        self.button_quit.add(self.hbox_quit)
        self.hbox_quit.pack_start(self.image_quit, padding=1)
        self.hbox_quit.pack_start(self.label_quit, padding=1)


# ===== Layout Configuration ======================================
        self.window.add(self.vbox_main)
        #self.window.set_size_request(250,250)

        self.vbox_main.pack_start(self.hbox_new,     False, True, 0)
        self.vbox_main.pack_start(self.vbox_hosts,   False, True, 0)
        self.vbox_main.pack_start(self.hbox_control, True,  True, 0)

        self.hbox_new.pack_start(self.entry_lport,   False, False, 0)
        self.hbox_new.pack_start(self.label_sep1,    False, False, 0)
        self.hbox_new.pack_start(self.entry_ip,      False, False, 0)
        self.hbox_new.pack_start(self.label_sep2,    False, False, 0)
        self.hbox_new.pack_start(self.entry_port,    False, False, 0)
        self.hbox_new.pack_start(self.combobox_type, False, False, 0)
        self.hbox_new.pack_start(self.button_add,    False, False, 0)

        self.hbox_control.pack_end(self.button_quit, False, False, 0)


# ===== Widget Configurations =====================================
        self.entry_lport.set_text("0")
        self.entry_lport.set_width_chars(5)
        self.entry_ip.set_text("")
        self.entry_ip.set_width_chars(20)
        self.entry_port.set_text("")
        self.entry_port.set_width_chars(5)
        self.combobox_type.append_text('TCP')
        self.combobox_type.append_text('UDP')
        self.combobox_type.set_active(1)

# ===== Event Bindings ============================================
        self.button_add.connect("clicked",  self.callback_add,  None)
        self.button_quit.connect("clicked", self.callback_quit, None)


# ===== Keyboard Shortcuts ========================================
        self.window.connect("key-press-event", self.callback_key_pressed)

        # Show widgets
        self.window.show_all()
        self.window.set_resizable(False)

        self.host_counter = Counter()

        if local:
            self.core = MultiPipe(log=log)
        else:
            self.dialog = gtk.Dialog(title="Select Tunneling Server", 
                                     buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                                              gtk.STOCK_OK,     gtk.RESPONSE_ACCEPT))
            if ASL:
                self.dialog.set_icon(asl.new_icon('upipe'))
            dialog_hbox = gtk.HBox()
            dialog_label = gtk.Label('Host:Port')
            dialog_entry_host  = gtk.Entry()
            dialog_label_colon = gtk.Label(':')
            dialog_entry_port  = gtk.Entry()

            dialog_entry_host.set_width_chars(20)
            dialog_entry_port.set_width_chars(5)

            dialog_hbox.pack_start(dialog_label,       False, False, 0)
            dialog_hbox.pack_start(dialog_entry_host,  False, False, 0)
            dialog_hbox.pack_start(dialog_label_colon, False, False, 0)
            dialog_hbox.pack_start(dialog_entry_port,  False, False, 0)

            self.dialog.vbox.pack_end(dialog_hbox)
            dialog_hbox.show_all()

            self.dialog.connect("key-press-event", self.callback_dialog_escape)
            dialog_entry_host.connect("key-press-event", self.callback_dialog_enter)
            dialog_entry_port.connect("key-press-event", self.callback_dialog_enter)

            response = self.dialog.run()
            host = dialog_entry_host.get_text()
            port = dialog_entry_port.get_text()
            self.dialog.destroy()

            if response == gtk.RESPONSE_ACCEPT:
                try:
                    host = socket.gethostbyname(host)
                except:
                    dialog = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                               buttons=gtk.BUTTONS_OK,
                                               message_format="Invalid host")
                    dialog.run()
                    dialog.destroy()
                    sys.exit(1)

                try:
                    port = int(port)
                    assert port > 0
                    assert port < 65536
                except:
                    dialog = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                               buttons=gtk.BUTTONS_OK,
                                               message_format="Invalid port")
                    dialog.run()
                    dialog.destroy()
                    sys.exit(1)

                address = (host, port)
                self.core = MultiPipeHosts(address, log=log, verbosity=verbosity)
            else:
                self.core = MultiPipe(log=log, verbosity=verbosity)

        # Start the asyncore manager thread
        self.core.start()


# ===== Callbacks =================================================
    def callback_key_pressed(self, widget, event, data=None):
        if event.state == gtk.gdk.MOD1_MASK:
            if event.keyval == ord('q'):
                self.close_application()

    def callback_dialog_escape(self, widget, event, data=None):
        if event.keyval == gtk.keysyms.Escape:
            self.dialog.response(gtk.RESPONSE_REJECT)

    def callback_dialog_enter(self, widget, event, data=None):
        if event.keyval == gtk.keysyms.Return:
            self.dialog.response(gtk.RESPONSE_ACCEPT)

    def callback_quit(self, widget, event, data=None):
        self.close_application()

    def callback_add(self, widget, event, data=None):
        try:
            lport = int(self.entry_lport.get_text())
        except:
            lport = None
        try:
            ip = socket.gethostbyname(self.entry_ip.get_text())
            port = int(self.entry_port.get_text())
            ptype = self.combobox_type.get_active_text()
            self._add_host(ip, port, ptype, lport)
        except:
            pass

    def callback_delete(self, widget, event, data=None):
        self._del_host(data)


# ===== Public Methods ============================================
    def close_application(self):
        self.core.stop()
        gtk.main_quit()
        return False

    def log(self, string, verbosity=1):
        self.core.log(string, verbosity)

# ===== Private Methods ===========================================
    def _add_host(self, host, port, ptype='UDP', local_port=None):
        ip = socket.gethostbyname(host)
        key = "%s-%d-%s" % (ip, port, ptype)
        if self.hosts.has_key(key):
            self.log('Host exists, cannot re-add...', 0)
            return
        self.core.add_host((ip, port), ptype, local_port)
        if not self.core._sockets.has_key(key):
            self.log('Failed to add new host...', 0)
            return
        host = {}
        host['vbox-host']     = gtk.VBox()
        host['hbox-host']     = gtk.HBox()
        host['vbox-clients']  = gtk.VBox()

        host['entry-lport']   = gtk.Entry()
        host['label-sep1']    = gtk.Label(":")
        host['entry-ip']      = gtk.Entry()
        host['label-sep2']    = gtk.Label(":")
        host['entry-port']    = gtk.Entry()
        host['entry-type']    = gtk.Entry()
        host['button-del']    = gtk.Button(stock=None)
        host['hbox-del']      = gtk.HBox()
        host['image-del']     = gtk.Image()
        host['image-del'].set_from_stock(gtk.STOCK_DELETE, gtk.ICON_SIZE_MENU)
        host['label-del']     = gtk.Label('Delete')
        host['button-del'].add(host['hbox-del'])
        host['hbox-del'].pack_start(host['image-del'], padding=1)
        host['hbox-del'].pack_start(host['label-del'], padding=1)

        self.vbox_hosts.pack_start(host['vbox-host'],       False, True, 0)
        host['vbox-host'].pack_start(host['hbox-host'],     False, True, 0)
        host['vbox-host'].pack_start(host['vbox-clients'],  False, True, 0)

        host['hbox-host'].pack_start(host['entry-lport'],   False, False, 0)
        host['hbox-host'].pack_start(host['label-sep1'],    False, False, 0)
        host['hbox-host'].pack_start(host['entry-ip'],      False, False, 0)
        host['hbox-host'].pack_start(host['label-sep2'],    False, False, 0)
        host['hbox-host'].pack_start(host['entry-port'],    False, False, 0)
        host['hbox-host'].pack_start(host['entry-type'],    False, False, 0)
        host['hbox-host'].pack_start(host['button-del'],    False, False, 0)

        host['entry-lport'].set_text(str(self.core._sockets[key].getsockname()[1]))
        host['entry-lport'].set_editable(False)
        host['entry-lport'].set_width_chars(5)
        host['entry-ip'].set_text(ip)
        #host['entry-ip'].set_text(host) # Host addition fails with this approach
        host['entry-ip'].set_editable(False)
        host['entry-ip'].set_width_chars(20)
        host['entry-port'].set_text(str(port))
        host['entry-port'].set_editable(False)
        host['entry-port'].set_width_chars(5)
        host['entry-type'].set_text(str(ptype))
        host['entry-type'].set_editable(False)
        host['entry-type'].set_width_chars(5)

        host['button-del'].connect("clicked", self.callback_delete, None, key)

        self.hosts[key] = host
        self.hosts[key]['vbox-host'].show_all()
        self.window.resize_children()

    def _del_host(self, key):
        if self.hosts.has_key(key):
            host = self.hosts[key]
            for k,_ in self.hosts[key].items():
                host[k].hide()
                del host[k]
            del self.hosts[key]
        self.core.del_host(key)
        self.window.resize_children()
        self.window.check_resize()

#/*}}}*/

# === main /*{{{*/
def main():
    pipe = None
    gui = None
    try:
        use_message = """usage: %prog [options] [args]
       U/C args -- udp_address udp_port
       S args   -- [tcp_port]"""
        option_list = []
        option_list.append(optparse.make_option("-a", "--address", dest="address", action="store", help="use this IP address if this is a client"))
        option_list.append(optparse.make_option("-g", "--gui", dest="gui", action="store_true", help="launch in graphical mode"))
        option_list.append(optparse.make_option("-l", "--log", dest="log", action="store_true", help="log traffic"))
        option_list.append(optparse.make_option("-p", "--port", dest="port", action="store", help="use this port for the TCP connection if this is a client"))
        option_list.append(optparse.make_option("-q", "--quiet", dest="quiet", action="store_true", help="Only report errors, no traffic information"))
        option_list.append(optparse.make_option("-t", "--type", dest="type", type="string", action="store", help="type of pipe (S, C, U) S=Server(Remote Facing) C=Client(Local Facing) U=Unified"))
        option_list.append(optparse.make_option("-v", action="count", dest="verbosity", help="specify multiple time to increase verbosity"))
        parser = optparse.OptionParser(option_list=option_list, usage=use_message)
        options, args = parser.parse_args()

        if options.quiet:
            verbosity = 0
        else:
            if options.verbosity is None:
                verbosity = 1
            else:
                verbosity = options.verbosity + 1

        if options.gui or (len(sys.argv) < 2):
            if not HAS_GUI:
                print "System does not support the GUI component."
                parser.print_help()
                sys.exit(1)
            local = False
            address = None
            if options.type == 'U':
                local = True
                #if len(args) < 2:
                #    parser.print_help()
                #    sys.exit(1)
                #ip   = args[0]
                #port = int(args[1])
                #address = (ip, port)
            gui = PipeUI(local=local, log=options.log, verbosity=verbosity)
            gtk.main()
        else:
            if options.type == 'S':
                ip   = ''
                port = 8000
                if len(args) > 0:
                    port = int(args[0])
                pipe = MultiPipeClients((ip, port), log=options.log, verbosity=verbosity)
            elif options.type == 'C':
                t_ip = '0.0.0.0'
                t_port = 8000
                if options.address:
                    t_ip = options.address
                if options.port:
                    t_port = int(options.port)
                if len(args) < 2:
                    parser.print_help()
                    sys.exit(1)
                ip   = args[0]
                port = int(args[1])
                pipe = MultiPipeHosts((t_ip, t_port), log=options.log, verbosity=verbosity)
                pipe.add_host((ip, port))
            else:
                if len(args) < 2:
                    parser.print_help()
                    sys.exit(1)
                ip   = args[0]
                port = int(args[1])
                pipe = MultiPipe(log=options.log, verbosity=verbosity)
                pipe.add_host((ip, port))
            pipe.run()
    except KeyboardInterrupt:
        print "Keyboard Interrupt [^C]"
        if gui:
            try: gui.close_application()
            except RuntimeError: pass
        if pipe:
            pipe.stop()
    except ExServerDied, e:
        print str(e)
    except Exception, e:
        print e
        if type(e) != tuple:
            raise
        elif len(e) != 2:
            raise
        elif e[0] != 9:
            raise
        else:
            pass

    #except Exception, e:
    #    print "Caught an unanticipated exception:"
    #    print str(e)
#/*}}}*/

if __name__ == "__main__":
    try:
        import psyco
        #psyco.full()
        psyco.profile()
        print "Psyco JIT enabled."
    except ImportError:
        pass

    main()

