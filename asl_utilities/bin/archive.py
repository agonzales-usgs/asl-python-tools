#!/usr/bin/env python
import asl

import asyncore
import calendar
import optparse
import os
import Queue
import re
import signal
import socket
import struct
import sys
import threading
import time
import traceback

from jtk.Class import Class
from jtk.Thread import Thread
from jtk.Logger import LogThread
from jtk import hexdump

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
class Status(asyncore.dispatcher, Class):
    def __init__(self, master, port=4000, log_queue=None):
        asyncore.dispatcher.__init__(self)
        Class.__init__(self, log_queue=log_queue)
        self.create_socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.bind(('', port))
        except:
            self.bind(('', 0))
        self._log("%s bound to port %d" % (self.__class__.__name__,self.getsockname()[1]))
        self._buffers = []
        self._write_buffer = ''
        self._write_address = None
        self._master = master
        self._regex_status = re.compile('^\[(.*)\]<(.*)>$')
        self._restart = False

    def handle_read(self):
        try:
            packet,address = self.recvfrom(4096)
        except socket.error:
            return
        if not packet:
            return 0
        match = self._regex_status.search(packet)
        if match:
            msg_id,message = match.groups()
        else:
            msg_id = '0'
            message = packet

        if message == 'RESTART':
            self._restart = True
            self._buffers.append(('[%s]<%d>' % (msg_id,os.getpid()), address))
            os.kill(os.getpid(), signal.SIGTERM)
        elif message == 'STATUS':
            self._buffers.append(('[%s]<ACTIVE>' % msg_id, address))
        elif message == 'LAST-PACKET':
            self._buffers.append(('[%s]<%d>' % (msg_id,self._master._last_packet_received), address))
        elif message == 'PID':
            self._buffers.append(('[%s]<%d>' % (msg_id,os.getpid()), address))
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
class LissReader(asyncore.dispatcher, Class):
    def __init__(self, master, log_queue=None):
        asyncore.dispatcher.__init__(self)
        Class.__init__(self, log_queue=log_queue)
        self._master = master
        self._connected = False
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.setblocking(0)

    def handle_connect(self):
        self._connected = True

    def handle_read(self):
        self._connected = True
        try:
            packet = self.recv(64)
        except socket.error, e:
            self.log("Socket Error: %s" % str(e))
            return 0
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
    def __init__(self, read_queue, status_port=4000, log_queue=None, name=None):
        Thread.__init__(self, queue_max=1024, log_queue=log_queue, name=name)
        self.daemon = True
        self.read_queue = read_queue
        self.socket = None
        self.address = ('127.0.0.1', 4000)
        self.buffer = None
        self.address_changed = False
        self.status = Status(self,status_port)
        self._last_packet_received = 0

    def restart_requested(self):
        return self.status._restart

    def get_status_port(self):
        return self.status.getsockname()[1]

    def set_status_port(self, port):
        if self.get_status_port() != port:
            self.status = Status(self,port)

    def get_address(self):
        return self.address

    def set_address(self, address):
        if self.address != address:
            self.address = address
            self.address_changed = True
            if self.running:
                self.notifier.notify()

    def set_port(self, new_port):
        host,port = self.address
        if port != new_port:
            self.set_address((host,new_port))

    def set_host(self, new_host):
        host,port = self.address
        if host != new_host:
            self.set_address((new_host,port))

    def halt_now(self):
        self.halt()

    def halt(self):
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
        self.notifier = Notifier()

        self.running = True
        last_print = 0
        print_frequency = 10 # every 10 seconds
        counts = {}
        while self.running:
            # If the LISS connection socket does not exist, create a new one.
            if self.socket == None:
                now = time.time()
                key = "%s:%d" % self.address
                if not counts.has_key(key):
                    counts[key] = 0
                counts[key] += 1
                if (now - last_print) >= print_frequency:
                    for addr_str,fail_count in counts.items():
                        self._log("%d failed attempt(s) to establish connection to %s" % (fail_count,addr_str), 'err')
                    last_print = now
                    counts = {}
                self.socket = LissReader(self, log_queue=self.log_queue)
                try:
                    self.socket.connect(self.address)
                except socket.error:
                    self._log("Could not establish LISS connection.", 'dbg')
                    del self.socket
                    self.socket = None
                    time.sleep(0.1)
                    continue

            map = {
                self.notifier.socket : self.notifier,
                self.socket.socket   : self.socket,
                self.status.socket   : self.status,
            }
            try:
                asyncore.loop(timeout=5.0, use_poll=False, map=map, count=1)
            except socket.error, e:
                self._log("asyncore.loop() socket.error: %s" % str(e), 'err')
                # If there is an issue with this socket, we need to create
                # a new socket. Set it to disconnected, and it will be replaced.
                self.socket._connected = False
                time.sleep(0.1)

            if self.address_changed:
                try:
                    self.socket.close()
                except:
                    pass
                self.address_changed = False
                time.sleep(0.1)
            # If the socket has been disconnected, prepare it for replacement.
            if not self.socket._connected:
                try:
                    self.socket.close()
                except:
                    pass
                del self.socket
                self.socket = None
                time.sleep(0.1)

        self.read_queue.put(('DONE', None))
# /*}}}*/

# === ReadThread Class /*{{{*/
class ReadThread(Thread):
    def __init__(self, write_queue, log_queue=None, name=None):
        Thread.__init__(self, log_queue=log_queue, name=name)
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

            # We should have a minimum of 64 bytes of data in order to continue
            # This provides us with room for a header and extensions
            while (self.buffer is not None) and (len(self.buffer) >= 64):
                index = struct.unpack('>H', self.buffer[46:48])[0]
                # If the index of the first blockette is beyond the end of our
                # buffer, we need to wait for more data to arrive
                if index >= (len(self.buffer) - 48):
                    break
                blockette_type = struct.unpack('>H', self.buffer[index:index+2])[0]
                # The first blockette for a SEED record should always be of type
                # 1000. If it is not, we skip to the next 64 byte group. 
                if blockette_type != 1000:
                    self._log("Invalid record. First blockette of a SEED record should always be type 1000.\n", 'err')
                    print hexdump.hexdump(self.buffer[:64], width=8)
                    self.buffer = self.buffer[64:]
                    continue
                # Check the length of the record so we know how much data to
                # collect before handing it off to the write thread.
                record_length = 2 ** struct.unpack('>B', self.buffer[index+6:index+7])[0]
                if record_length < 64:
                    self._log("Invalid record. Record length field must be 64 (bytes) or greater.\n", 'err')
                    self.buffer = self.buffer[64:]
                    continue
                # If the buffer contains more data than the length of a single
                # record, pull the record off for processing, and leave the
                # rest in the buffer
                if record_length < len(self.buffer):
                    record = self.buffer[0:record_length]
                    self.buffer = self.buffer[record_length:]
                # If the buffer contains only the record, empty it
                elif record_length == len(self.buffer):
                    record = self.buffer
                    self.buffer = None
                # If we do not have a full record's worth of data, wait until 
                # more data arrives
                else:
                    break

                # Break down the record header
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
                    self._log("Record # %s (%s_%s %s-%s) %u,%u %02u:%02u:%02u.%04u (count[%d] factor[%d] multiplier[%d])" % (seq_num, st_net, st_name, ch_loc, ch_name, y, d, h, m, s, t, sample_count, rate_factor, rate_multiplier), 'dbg')
                    rate *= 10000

                if y < 1 or d < 1:
                    self._log("Found a bad date (%04u,%03u %02u:%02u:%02u.%04u).\n" % (y,d,h,m,s,t), 'warn')
                    b_time = 0
                else:
                    b_time = int(calendar.timegm(time.strptime("%04u,%03u,%02u:%02u:%02u" % (y,d,h,m,s), "%Y,%j,%H:%M:%S"))) * 10000 + t

                if (activity_flags & 0x02) == 0:
                    b_time += time_correction
                e_time = b_time + rate * (sample_count - 1)

                # Send record to write thread
                self.write_queue.put(('WRITE',(seq_num,st_net,st_name,ch_loc,ch_name,b_time,e_time,record)))

                #year,jday,hour,min,sec,_,tmsec = b_time
                #position = self.fh.tell()
                #self._log("Record %d [%d:%d] {%d:%d} " % (record_count,(position-record_length)/record_length,position/record_length,position-record_length,position), 'dbg')
                #self._log("[%04u,%03u %02u:%02u:%02u.%04u]" % (year, jday, hour, min, sec, tmsec), 'dbg')
                #self._log("\n", 'dbg')

        except KeyboardInterrupt:
            pass
        except Exception, e:
            exc_type,exc_value,exc_traceback = sys.exc_info()
            self._log(traceback.format_exc(), 'err')

#/*}}}*/

# === WriteThread Class /*{{{*/
class WriteThread(Thread):
    def __init__(self, log_queue=None, name=None):
        Thread.__init__(self, queue_max=1024, log_queue=log_queue, name=name)
        self.stations = {}
        self.target_dir = ''
        self.last_report = time.time()
        self.records = {}
        self.year_in_day_path = False

    def set_year_in_day_path(self, enable):
        self.year_in_day_path = enable

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

            now = time.time()
            last_tm = time.gmtime(self.last_report)
            now_tm = time.gmtime(now)
            if now_tm.tm_hour > last_tm.tm_hour or \
               now_tm.tm_yday > last_tm.tm_yday or \
               now_tm.tm_year > last_tm.tm_year:
                self._log("Records received/written (%s - %s):" % (time.strftime("%H:%M:%S", last_tm), time.strftime("%H:%M:%S", now_tm)))
                max_key = max(map(len, self.records.keys()))
                for k in sorted(self.records.keys()):
                    r = self.records[k]['r']
                    w = self.records[k]['w']
                    if r > 0:
                        self._log("  %s: %d/%d" % (k.ljust(max_key),r,w))
                self.records = {}
                self.last_report = now
            

            file_handle = None

            network,station,location,channel = tuple(map(str.strip, data[1:5]))
            record = data[7]
            rec_len = len(record)
            st_dir = "%s_%s" % (network,station)
            loc_str = ""
            if len(location) > 0:
                loc_str = "%s_" % location
            ch_file = "%s%s.%d.seed" % (loc_str,channel,rec_len)
            date = time.strftime("%Y/%j", time.gmtime(data[5] / 10000))
            date_path = date
            if self.year_in_day_path:
                y,d = date.split('/')
                date_path = "%s/%s_%s" % (y,y,d)

            if not self.records.has_key(st_dir):
                self.records[st_dir] = {'r' : 0, 'w' : 0}
            self.records[st_dir]['r'] += 1

            # Select the mapping for this station
            if not self.stations.has_key(st_dir):
                self.stations[st_dir] = {}
            file_handles = self.stations[st_dir]

            # If there is already a file open for this channel
            # retrieve it
            if file_handles.has_key(ch_file):
                file_date,file_handle = file_handles[ch_file]
                # If this date is no longer valid, close the file
                if date != file_date:
                    file_handle.close()
                    file_handle = None
                    del file_handles[ch_file]

            # If the file handle for this station+channel is not open, open it
            if file_handle is None:
                target_dir = "%s/%s/%s" % (self.target_dir, st_dir, date_path)
                if not os.path.exists(target_dir):
                    try:
                        self._log("Creating new directory '%s'" % target_dir)
                        os.makedirs(target_dir)
                    except:
                        self._log("Could not create archive directory '%s'" % target_dir, 'err')
                        raise Exception("Could not create archive directory")
                if not os.path.isdir(target_dir):
                    self._log("Path '%s' exists, but it is not a directory" % target_dir, 'err')
                    raise Exception("Archive path exists, but it is not a directory")
                file = "%s/%s" % (target_dir, ch_file)
                if os.path.exists(file):
                    try:
                        self._log("Opening existing file '%s'" % file, 'dbg')
                        file_handles[ch_file] = (date,open(file, 'a+b'))
                    except:
                        self._log("Could not open file '%s' for appending" % file, 'err')
                        raise Exception("Could not append to archive file")
                else:
                    try:
                        self._log("Creating new file '%s'" % file, 'dbg')
                        file_handles[ch_file] = (date,open(file, 'w+b'))
                    except:
                        self._log("Could not create file '%s'" % file, 'err')
                        raise Exception("Could not create archive file")
                file_handle = file_handles[ch_file][1]

            self._log("Writing %d bytes for %s_%s %s-%s" % (rec_len,network,station,location,channel), 'dbg')
            file_handle.write(record)
            file_handle.flush()

            self.records[st_dir]['w'] += 1

        except KeyboardInterrupt:
            pass
        except Exception, e:
            exc_type,exc_value,exc_traceback = sys.exc_info()
            self._log(traceback.format_exc(), 'err')
#/*}}}*/

# === Main Class /*{{{*/
class Main(Class):
    def __init__(self):
        Class.__init__(self)
        self.context = {'running' : False}
        signal.signal(signal.SIGTERM, self.halt_now)
        self.context['log'] = LogThread(prefix='archive_', note='ARCHIVE', pid=True)
        self.context['log'].start()
        self.log_queue = self.context['log'].queue
        self.already_running = False
        # INFO: Can use the self._log() method after this point only  

    def start(self):
        try:
            use_message = """usage: %prog [options]"""
            option_list = []
            option_list.append(optparse.make_option("-c", "--config-file", dest="config_file", action="store", help="use this configuration file instead of the default"))
            parser = optparse.OptionParser(option_list=option_list, usage=use_message)
            options, args = parser.parse_args()

            self.context['write'] = WriteThread(log_queue=self.context['log'].queue)
            self.context['read']  = ReadThread(self.context['write'].queue, log_queue=self.context['log'].queue)
            self.context['liss']  = LissThread(self.context['read'].queue, log_queue=self.context['log'].queue)

            archive_path = ''
            config_file  = ''
            configuration = {}
            if options.config_file:
                config_file = options.config_file
            if not os.path.exists(config_file):
                if os.environ.has_key('SEED_ARCHIVE_CONFIG'):
                    config_file = os.environ['SEED_ARCHIVE_CONFIG']
            if not os.path.exists(config_file):
                config_file = 'archive.config'
            if not os.path.exists(config_file):
                config_file = '/opt/etc/archive.config'
            if os.path.exists(config_file):
                try:
                    fh = open(config_file, 'r')
                    lines = fh.readlines()
                    for line in lines:
                        if line[0] == '#':
                            continue
                        line = line.split('#',1)[0]
                        parts = tuple(map(lambda p: p.strip(), line.split('=',1)))
                        if len(parts) != 2:
                            continue
                        k,v = parts
                        configuration[k] = v
                except:
                    pass

            log_path = ''
            try: # Check for log directory
                log_path = os.path.abspath(configuration['log-path'])
                #self._log("log directory is '%s'" % log_path)
            except Exception, e:
                self._log("Config [log]:> %s" % (str(e),))

            try: # Check for archive directory
                archive_path = os.path.abspath(configuration['archive-path'])
                #self._log("archive directory is '%s'" % archive_path)
            except Exception, e:
                self._log("Config [log]:> %s" % (str(e),))

            if not os.path.isdir(archive_path):
                if os.environ.has_key('SEED_ARCHIVE_DIRECTORY'):
                    archive_path = os.environ['SEED_ARCHIVE_DIRECTORY']
            if not os.path.isdir(archive_path):
                archive_path = '/opt/data/archive'
            if not os.path.exists(archive_path):
                self._log("Archive directory '%s' does not exist. Exiting!" % archive_path)
                raise KeyboardInterrupt()

            year_in_day_path = False
            if configuration.has_key('archive-year-in-day-path') and \
               configuration['archive-year-in-day-path'].lower() == 'true':
                year_in_day_path = True
            self.context['write'].set_year_in_day_path(year_in_day_path)

            if not os.path.exists(log_path):
                log_path = archive_path

            self.context['log'].logger.set_log_path(log_path)

            #self._log("Configuration file is '%s'" % (config_file,))
            #self._log("Configuration contents: %s" % (str(configuration),))

            try: # Check for screen logging
                if configuration['log-to-screen'].lower() == 'true':
                    self.context['log'].logger.set_log_to_screen(True)
                    str_screen_logging = "Enabled"
                else:
                    self.context['log'].logger.set_log_to_screen(False)
                    str_screen_logging = "Disabled"
            except Exception, e:
                self._log("Config [log-to-screen]:> %s" % (str(e),))

            try: # Check for file logging
                if configuration['log-to-file'].lower() == 'true':
                    self.context['log'].logger.set_log_to_file(True)
                    str_file_logging = "Enabled"
                else:
                    self.context['log'].logger.set_log_to_file(False)
                    str_file_logging = "Disabled"
            except Exception, e:
                self._log("Config [log-to-file]:> %s" % (str(e),))

            try: # Check for debug logging
                if configuration['log-debug'].lower() == 'true':
                    self.context['log'].logger.set_log_debug(True)
                    str_debug_logging = "Enabled"
                else:
                    self.context['log'].logger.set_log_debug(False)
                    str_debug_logging = "Disabled"
            except Exception, e:
                self._log("Config [log-debug]:> %s" % (str(e),))

            # Check for an archive process already writing to this location.
            running = False
            pid_file = os.path.abspath("%s/archive.pid" % archive_path)
            if os.path.isfile(pid_file):
                tpid = open(pid_file, 'r').read(32).strip()
                ipid = -1
                try:
                    ipid = int(tpid)
                except:
                    pass
                if (ipid != os.getpid()) and find_proc(tpid):
                    restart_path = os.path.abspath("%s/restart.%s" % (archive_path,tpid))
                    running = True
                    if os.path.exists(restart_path):
                        if os.path.isfile(restart_path):
                            os.remove(restart_path)
                            kill_proc(tpid, log=self._log)
                            running = False
                        else:
                            self._log("Invalid type for restart file %s" % restart_path)
            if running:
                self._log("archive.py process [%s] is already running" % tpid, 'dbg')
                self.already_running = True
                raise KeyboardInterrupt

            self._log("===============")
            self._log("=== ARCHIVE ===")
            self._log("===============")

            pid = os.getpid()
            self._log("starting new archive.py process [%d]" % pid)
            fh = open(pid_file, 'w+')
            fh.write('%s\n' % str(pid))
            fh.close()

            port = 0
            try: # Get LISS port
                port = int(configuration['liss-port'])
                if 0 < port < 65536:
                    self.context['liss'].set_port(port)
            except Exception, e:
                self._log("Config [liss-port]:> %s" % (str(e),))

            host = ''
            try: # Get LISS host
                host = configuration['liss-host']
                host = socket.gethostbyname(host)
                self.context['liss'].set_host(host)
            except Exception, e:
                self._log("Config [liss-host]:> %s" % (str(e),))

            status_port = 4000
            try: # Get Status port
                status_port = int(configuration['status-port'])
                if 0 < port < 65536:
                    self.context['liss'].set_status_port(status_port)
            except Exception, e:
                self._log("Config [status-port]:> %s" % (str(e),))

            self.context['write'].set_target_dir(archive_path)

            self._log("LISS archive process for host %s:%d" % self.context['liss'].get_address())
            self._log("     Configuration : %s" % (config_file,))
            self._log(" Archive Directory : %s" % (archive_path,))
            self._log("     Log Directory : %s" % log_path)
            self._log("    Screen Logging : %s" % str_screen_logging)
            self._log("      File Logging : %s" % str_file_logging)
            self._log("     Debug Logging : %s" % str_debug_logging)

            self.context['write'].start()
            self.context['read'].start()
            self.context['liss'].start()

            self.context['running'] = True

            self._log("       Status Port : %s" % str(self.context['liss'].get_status_port()))

            self._log("----------------")
            self._log("--- Contexts ---")
            contexts = ['log','write','read','liss','running']
            max_key = max(map(len, contexts))
            for key in contexts:
                context = self.context[key]
                if type(context) == bool:
                    self._log("  %s : %s" % (key.rjust(max_key), str(context)))
                else:
                    self._log("  %s : %s (%s)" % (key.rjust(max_key), context.name, T(context.is_alive(),"Running","Halted")))

            while self.context['running']:
                try: 
                    signal.pause()
                    self._log("caught a signal")
                except:
                    time.sleep(1.0)

                if self.context['liss'].restart_requested():
                    self.halt_now()
        except KeyboardInterrupt:
            pass

        halted = False
        while not halted:
            try:
                self.halt()
                halted = True
            except KeyboardInterrupt:
                pass

    def halt(self, now=False):
        check_alive = lambda c,k: c.has_key(k) and c[k] and c[k].isAlive()
        thread_list = ['liss', 'read', 'write', 'log']
        for key in thread_list:
            if not self.already_running:
                self._log("halting %s..." % self.context[key].name)
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

# === Functions/*{{{*/
def print_func(string, *args):
    print string

def kill_proc(tpid, log=print_func):
    if find_proc(tpid):
        log("archive.py process [%s] found" % tpid)
        log("sending SIGTERM to archive.py process [%s]" % tpid)
        os.kill(int(tpid), 15)
        count = 60
        while 1:
            if not find_proc(tpid):
                log("archive.py process [%s] has died" % tpid)
                break
            count -= 1
            if count <= 0:
                log("sending SIGKILL to archive.py process [%s]" % tpid)
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
#/*}}}*/

def T(s,t,f):
    if s: return t
    return f

def main():
    main = Main()
    main.start()

if __name__ == '__main__':
    main()
        

