#!/usr/bin/env python
import asl

import asyncore
import calendar
import os
import Queue
import re
import signal
import socket
import struct
import sys
import threading
import time

from jtk.Class import Class
from jtk.Thread import Thread
from jtk.Logger import LogThread

# === Notifier Class /*{{{*/
class Notifier(asyncore.dispatcher):
    def __init__(self):
        asyncore.dispatcher.__init__(self)
        self.sock_in = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_in.bind(('', 0))
        self.address = ('127.0.0.1', self.sock_in.getsockname()[1])
        self.sock_out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.set_socket(self.sock_in)

    def notify(self):
        self.sock_out.sendto('CHANGED', self.address)

    def handle_read(self):
        msg = self.sock_in.recv(7)
        return len(msg)

    def writable(self):
        return False
#/*}}}*/

# === Status Class /*{{{*/
class Status(asyncore.dispatcher):
    def __init__(self, master, log_queue=None):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.bind(('', 4000))
        self._buffers = []
        self._write_buffer = ''
        self._write_address = None
        self._master = master
        self._regex_status = re.compile('^\[(.*)\]<(.*)>$')

    def handle_read(self):
        try:
            packet,address = self.recvfrom(4096)
        except socket.error:
            time.sleep(1.0)
            return
        if not packet:
            return 0
        match = self._regex_status.search(packet)
        if match:
            id,message = match.groups()
        else:
            id = '0'
            message = packet

        if message == 'STATUS':
            self._buffers.append(('[%s]<ACTIVE>' % id, address))
        elif message == 'LAST-PACKET':
            self._buffers.append(('[%s]<%d>' % (id,self._master._last_packet_received), address))
        elif message == 'PID':
            self._buffers.append(('[%s]<%d>' % (id,getpid()), address))
        else:
            self._buffers.append(('[-1]<UNRECOGNIZED>', address))
        return len(packet)

    def handle_write(self):
        bytes_written = 0
        if (self._write_address is None) or (not len(self._write_buffer)):
            if len(self._buffers):
                self._write_buffer,self._write_address = self._buffers.pop(0)
            else:
                self._write_buffer = ''
                self._write_address = None
        if (self._write_address is not None) and len(self._write_buffer):
            bytes_written = self.sendto(self._write_buffer, self._write_address)
        self._write_buffer = self._write_buffer[bytes_written:]

    def readable(self):
        return True

    def writable(self):
        if len(self._buffers):
            return True
        if len(self._write_buffer) and self._write_address is not None:
            return True
        return False

#/*}}}*/

# === LissReader Class /*{{{*/
class LissReader(asyncore.dispatcher):
    def __init__(self, master):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self._connected = False
        self._master = master
        self.setblocking(0)

    def handle_connect(self):
        self._connected = True

    def handle_read(self):
        try:
            packet = self.recv(64)
        except socket.error:
            time.sleep(1.0)
            return
        self._master.queue_packet(packet)
        self._master._last_packet_received = calendar.timegm(time.gmtime())
        if not packet:
            return 0
        return len(packet)

    def handle_close(self):
        self._connected = False

    def writable(self):
        return False
#/*}}}*/

# === LissThread Class /*{{{*/
class LissThread(Thread):
    def __init__(self, read_queue, log_queue=None):
        Thread.__init__(self, queue_max=1024, log_queue=log_queue)
        self.daemon = True
        self.read_queue = read_queue
        self.socket = None
        self.address = ('127.0.0.1', 4000)
        self.buffer = None
        self.address_changed = False
        self._last_packet_received = 0

    def set_address(self, address):
        if self.address != address:
            self.address = address
            self.address_changed = True

    def halt_now(self):
        self.halt()

    def halt(self):
        self._log("thread halting...")
        self.running = False
        self.notifier.notify()

    def queue_packet(self, packet):
        if packet is None:
            return
        if self.buffer == None:
            self.buffer = packet
        else:
            self.buffer += packet
        while self.buffer and (len(self.buffer) >= 64):
            self.read_queue.put(('READ', self.buffer[0:64]))
            if len(self.buffer) == 64:
                self.buffer = None
            else:
                self.buffer = self.buffer[64:]

    def run(self):
        self.running = True
        self.notifier = Notifier()
        self.status = Status(self)
        while self.running:
            if self.socket == None:
                self.socket = LissReader(self)
                self.socket.bind(('', 0))
                try:
                    self.socket.connect(self.address)
                except socket.error:
                    del self.socket
                    self.socket = None
                    time.sleep(1.0)
                    continue
            map = {
                self.notifier.socket : self.notifier,
                self.socket.socket   : self.socket,
                self.status.socket   : self.status,
            }
            #asyncore.loop(timeout=30.0, use_poll=False, map=map, count=1)
            asyncore.loop(timeout=5.0, use_poll=False, map=map, count=1)

            if self.address_changed:
                try:
                    self.socket.close()
                except:
                    pass
                self.address_changed = False
            if not self.socket._connected:
                try:
                    self.socket.close()
                except:
                    pass
                del self.socket
                self.socket = None

        self.read_queue.put(('DONE', None))
# /*}}}*/

# === ReadThread Class /*{{{*/
class ReadThread(Thread):
    def __init__(self, write_queue, log_queue=None):
        Thread.__init__(self, log_queue=log_queue)
        self.write_queue = write_queue
        self.buffer = None

    def _run(self, message, data):
        try:
            if message != 'READ':
                self._log("Invalid message '%s'" % message, 'warn')
                return
            # [q] SequenceNumber
            # [n] Network 
            # [s] Station
            # [l] Location
            # [c] Channel
            # [b] Begin timestamp
            # [e] End timestamp
            # [r] Record
            #f,q,n,s,l,c,b,e,r = data

            if data is None:
                self._log("_run() data is 'None'")
                return

            try:
                self.buffer += data
            except:
                self.buffer = data

            if self.buffer is None:
                self._log("_run() buffer is 'None'", 'debug')
                return

            while (self.buffer is not None) and (len(self.buffer) >= 64):
                index = struct.unpack('>H', self.buffer[46:48])[0]
                if index >= (len(self.buffer) - 48):
                    break
                blockette_type = struct.unpack('>H', self.buffer[index:index+2])[0]
                if blockette_type != 1000:
                    self._log("Invalid record. First blockette of a SEED record should always be type 1000.\n", 'err')
                    self.buffer = self.buffer[64:]
                    continue
                record_length = 2 ** struct.unpack('>B', self.buffer[index+6:index+7])[0]
                if record_length < 64:
                    self._log("Invalid record. Record length field must be 64 bytes or greater.\n", 'err')
                    self.buffer = self.buffer[64:]
                    continue
                if record_length < len(self.buffer):
                    record = self.buffer[0:record_length]
                    self.buffer = self.buffer[record_length:]
                elif record_length == len(self.buffer):
                    record = self.buffer
                    self.buffer = None
                else:
                    break

                seq_num, _, _, st_name, ch_loc, ch_name, st_net, y, d, h, m, s, _, t, sample_count, rate_factor, rate_multiplier, activity_flags, _, _, _, time_correction, _, _ = struct.unpack('>6scc5s2s3s2sHHBBBBHHhhBBBBlHH', record[0:48]) 

                if rate_factor == 0:
                    self._log("Found sample rate factor of zero.\n", 'dbg')
                    rate = 0
                elif rate_multiplier == 0:
                    self._log("Found sample rate multiplier of zero.\n", 'dbg')
                    rate = 0
                else:
                    if rate_factor > 0:
                        if rate_multiplier < 0:
                            rate = 1.0 / float(rate_factor) / float(rate_multiplier)
                        else:
                            rate = 1.0 / float(rate_factor) * float(rate_multiplier)
                    else:
                        if rate_multiplier < 0:
                            rate = float(rate_factor) / float(rate_multiplier)
                        else:
                            rate = float(rate_factor) * float(rate_multiplier)
                    #self._log("Record # %s (%s_%s %s-%s) %u,%u %02u:%02u:%02u.%04u (count[%d] factor[%d] multiplier[%d])" % (seq_num, st_net, st_name, ch_loc, ch_name, y, d, h, m, s, t, sample_count, rate_factor, rate_multiplier))
                    rate *= 10000

                if y < 1 or d < 1:
                    self._log("Found a bad date (%04u,%03u %02u:%02u:%02u.%04u).\n" % (y,d,h,m,s,t), 'warn')
                    b_time = 0
                else:
                    b_time = int(calendar.timegm(time.strptime("%04u,%03u,%02u:%02u:%02u" % (y,d,h,m,s), "%Y,%j,%H:%M:%S"))) * 10000 + t

                if (activity_flags & 0x02) == 0:
                    b_time += time_correction
                e_time = b_time + rate * (sample_count - 1)

                # Send record to handler thread
                self.write_queue.put(('WRITE',(seq_num,st_net,st_name,ch_loc,ch_name,b_time,e_time,record)))

                #year,jday,hour,min,sec,_,tmsec = b_time
                #position = self.fh.tell()
                #self._log("Record %d [%d:%d] {%d:%d} " % (record_count,(position-record_length)/record_length,position/record_length,position-record_length,position), 'dbg')
                #self._log("[%04u,%03u %02u:%02u:%02u.%04u]" % (year, jday, hour, min, sec, tmsec), 'dbg')
                #self._log("\n", 'dbg')

        except KeyboardInterrupt:
            pass
        except Exception, e:
            self._log("_run() Exception: %s" % str(e), 'err')

#/*}}}*/

# === WriteThread Class /*{{{*/
class WriteThread(Thread):
    def __init__(self, log_queue=None):
        Thread.__init__(self, queue_max=1024, log_queue=log_queue)
        self.file_handles = {}
        self.target_dir = ''

    def set_target_dir(self, target_dir):
        self.target_dir = target_dir

    def _run(self, message, data):
        try:
            # [q] SequenceNumber
            # [n] Network 
            # [s] Station
            # [l] Location
            # [c] Channel
            # [b] Begin timestamp
            # [e] End timestamp
            # [r] Record
            #q,n,s,l,c,b,e,r = data
            if message != 'WRITE':
                self._log("Invalid message '%s'" % message, 'warn')
                return

            file_handle = None
            key = "%s_%s_%s_%s" % tuple(map(str.strip, data[1:5]))
            date = time.strftime("%Y/%j", time.gmtime(data[5] / 10000))

            if self.file_handles.has_key(key):
                file_date,file_handle = self.file_handles[key]
                if date != file_date:
                    file_handle.close()
                    file_handle = None
                    del self.file_handles[key]

            if file_handle is None:
                target_dir = self.target_dir + "/" + date
                if not os.path.exists(target_dir):
                    try:
                        os.makedirs(target_dir)
                    except:
                        self._log("Could not create archive directory '%s'" % target_dir)
                        raise Exception("Could not create archive directory")
                if not os.path.isdir(target_dir):
                    self._log("Path '%s' is not a directory" % target_dir)
                    raise Exception("Archive path exists, but it is not a directory")
                file = target_dir + '/' + key + '.seed'
                if os.path.exists(file):
                    try:
                        self.file_handles[key] = (date,open(file, 'a+b'))
                    except:
                        self._log("Could not open file '%s' for appending" % target_dir)
                        raise Exception("Could not append to archive file")
                else:
                    try:
                        self.file_handles[key] = (date,open(file, 'w+b'))
                    except:
                        self._log("Could not create file '%s'" % target_dir)
                        raise Exception("Could not create archive file")
                file_handle = self.file_handles[key][1]

            record = data[7]
            self._log("Writing %d bytes for %s" % (len(record), key), 'dbg')
            file_handle.write(record)
            file_handle.flush()
        except KeyboardInterrupt:
            pass
        except Exception, e:
            self._log("_run() Exception: %s" % str(e), 'err')
#/*}}}*/

# === Main Class /*{{{*/
class Main(Class):
    def __init__(self):
        Class.__init__(self)
        self.context = {'running' : False}
        signal.signal(signal.SIGTERM, self.halt_now)
        self.context['log'] = LogThread()
        self.context['log'].start()
        self.log_queue = self.context['log'].queue
        # INFO: Can use the self._log() method after this point only  

    def start(self):
        try:

            self.context['write'] = WriteThread(self.context['log'].queue)
            self.context['read']  = ReadThread(self.context['write'].queue, self.context['log'].queue)
            self.context['liss']  = LissThread(self.context['read'].queue, self.context['log'].queue)

            archive_path = ''
            if os.environ.has_key('ARCHIVE_DIRECTORY'):
                archive_path = os.environ['ARCHIVE_DIRECTORY']
            if not os.path.isdir(archive_path):
                archive_path = '/opt/data/archive'

            self.context['write'].set_target_dir(archive_path)

            self.context['write'].start()
            self.context['read'].start()
            self.context['liss'].start()

            self.context['running'] = True

            while self.context['running']:
                try: 
                    signal.pause()
                    self._log("caught a signal")
                except:
                    time.sleep(1.0)
        except KeyboardInterrupt:
            pass

        halted = False
        while not halted:
            try:
                self.halt_now()
                halted = True
            except KeyboardInterrupt:
                pass

    def halt(self, now=False):
        check_alive = lambda c,k: c.has_key(k) and c[k] and c[k].isAlive()
        thread_list = ['liss', 'read', 'write', 'log']
        for key in thread_list:
            if check_alive(self.context, key):
                if now:
                    self.context[key].halt_now()
                else:
                    self.context[key].halt()
                self.context[key].join()
        self.context['running'] = False

    def halt_now(self, signal=None, frame=None):
        self.halt(True)
#/*}}}*/

def kill_proc(tpid):
    if find_proc(tpid):
        print "archive.py process [%s] found" % tpid
        print "sending SIGTERM to archive.py process [%s]" % tpid
        os.kill(int(tpid), 15)
        count = 60
        while 1:
            if not find_proc(tpid):
                print "archive.py process [%s] has died" % tpid
                break
            count -= 1
            if count <= 0:
                print "sending SIGKILL to archive.py process [%s]" % tpid
                os.kill(int(tpid), 9)
                break
                time.sleep(1.0)

def find_proc(tpid):
    tpid = str(tpid)
    proc = os.popen('ps ax -o pid,args | grep %s' % tpid)
    for line in proc.readlines():
        pid,exe = line.strip().split(' ', 1)
        if tpid == pid:
            if re.search('archive[.]py', exe):
                return True
    return False

def main():
    running = False
    if os.path.exists('/tmp/archive.pid'):
        tpid = open('/tmp/archive.pid', 'r').read(32).strip()
        proc = os.popen('ps x -o pid,args | grep %s' % tpid)
        for line in proc.readlines():
            pid,exe = line.strip().split(' ', 1)
            if tpid == pid:
                restart_path = '/opt/var/archive/restart/%s' % tpid
                if re.search('archive[.]py', exe):
                    if os.path.exists(restart_path):
                        if os.path.isfile(restart_path):
                            os.remove(restart_path)
                            kill_proc(tpid)
                            continue
                        else:
                            print "invalid type for restart file %s" % restart_path
                    print "archive.py process [%s] already running" % tpid
                    running = True

    if not running:
        pid = os.getpid()
        print "starting new archive.py process [%d]" % pid
        fh = open('/tmp/archive.pid', 'w+')
        fh.write('%s\n' % str(pid))
        fh.close()

        main = Main()
        main.start()

if __name__ == '__main__':
    main()
        

