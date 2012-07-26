#!/usr/bin/env python
import asl

import asyncore
import optparse
import os
import Queue
import re
import signal
import socket
import sys
import time
import traceback

from jtk import Config
from jtk.Class import Class
from jtk.Thread import Thread
from jtk.Logger import LogThread
from jtk import hexdump

# === Functions/*{{{*/
def print_func(string, *args):
    print string

def T(s,t,f):
    if s: return t
    return f
        
def find_process(arg_list):
    #print "searching for process with arguments:", arg_list
    pid = None
    proc = os.popen("ps x -o pid,args")
    for line in proc.readlines():
        tpid,rest = line.strip().split(None, 1)
        args = rest.split()
        if len(args) != len(arg_list):
            continue

        found = True
        for a,b in zip(arg_list, args):
            if a != b:
                #print "  '%s' != '%s'" % (a, b)
                found = False
                break
            else:
                #print "  '%s' == '%s'" % (a, b)
                pass
        if not found:
            continue

        pid = tpid
        break

    return pid

def find_proc(tpid):
    tpid = str(tpid)
    proc = os.popen('ps ax -o pid,args | grep %s' % tpid)
    for line in proc.readlines():
        pid,exe = line.strip().split(' ', 1)
        if tpid == pid:
            if re.search('processes[.]py', exe):
                return True
    return False

def kill_proc(tpid, log=print_func):
    if find_proc(tpid):
        log("processes.py process [%s] found" % tpid)
        log("sending SIGTERM to processes.py process [%s]" % tpid)
        os.kill(int(tpid), 15)
        count = 60
        while 1:
            if not find_proc(tpid):
                log("processes.py process [%s] has died" % tpid)
                break
            count -= 1
            if count <= 0:
                log("sending SIGKILL to processes.py process [%s]" % tpid)
                os.kill(int(tpid), 9)
                break
                time.sleep(1.0)
#/*}}}*/

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

# === CommHandler Class /*{{{*/
class CommHandler(asyncore.dispatcher, Class):
    def __init__(self, master, bind_port, bind_ip, log_queue=None):
        asyncore.dispatcher.__init__(self)
        Class.__init__(self, log_queue=log_queue)
        self.create_socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.bind((bind_ip, bind_port))
        except:
            raise Exception("Failed to bind to control port %d" % bind_port)
        i,p = self.getsockname()
        self._log("%s bound to %s:%d" % (self.__class__.__name__,i,p))
        self._master = master
        self._regex_status = re.compile('^\[(.*)\]<(.*)>$')

        self._request_queue = Queue.Queue()
        self._reply_queue = Queue.Queue()
        self._awaiting_reply = {}

    def request(self, block=True, timeout=None):
        result = None
        try:
            result = self._request_queue.get(block, timeout)
        except Queue.Empty:
            pass
        return result

    def reply(self, key, message):
        if not self._awaiting_reply.has_key(key):
            self._log("key '%s' not found, reply not sent" % key)
            return
        address,msg_id = self._awaiting_reply[key]
        del self._awaiting_reply[key]
        self._reply_queue.put(('[%s]<%s>' % (msg_id, message), address))
        self._master.notify()

    def handle_read(self):
        self._log("handle_read()")
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
            msg_id = None
            message = None

        if message is None:
            msg_id = None

        host,port = address
        key = "%s-%d-%s" % (host, port, str(msg_id))
        self._awaiting_reply[key] = (address, msg_id)

        if msg_id is None:
            self._reply_queue.put(("[-1]<UNRECOGNIZED>", address))
        else:
            self._request_queue.put((key, message))

        return len(packet)

    def handle_write(self):
        self._log("handle_write()")
        try:
            reply,address = self._reply_queue.get_nowait()
            bytes_written = self.sendto(reply, address)
        except Queue.Empty:
            pass

    # Always ready for new data
    def readable(self):
        return True

    # Only ready when replys are in the queue
    def writable(self):
        return not self._reply_queue.empty()

#/*}}}*/

# === CommThread Class /*{{{*/
class CommThread(Thread):
    def __init__(self, master, bind_port, bind_ip, log_queue=None, name=None):
        Thread.__init__(self, queue_max=1024, log_queue=log_queue, name=name)
        self._master = master
        self.daemon = True
        self.handler = CommHandler(self, bind_port, bind_ip, log_queue=log_queue)
        self._last_packet_received = 0

    def notify(self):
        self.notifier.notify()

    def halt_now(self):
        self.halt()

    def halt(self):
        self.running = False
        self.notify()

    def run(self):
        self.notifier = Notifier()

        self.running = True
        last_print = 0
        print_frequency = 10 # every 10 seconds
        counts = {}
        while self.running:

            map = {
                self.notifier.socket : self.notifier,
                self.handler.socket  : self.handler,
            }
            try:
                asyncore.loop(timeout=5.0, use_poll=False, map=map, count=1)
            except socket.error, e:
                self._log("asyncore.loop() socket.error: %s" % str(e), 'err')
                # If there is an issue with this socket, we need to create
                # a new socket. Set it to disconnected, and it will be replaced.

# /*}}}*/

# === ControlThread Class /*{{{*/
class ControlThread(Thread):
    def __init__(self, master, comm, log_queue=None, name=None, queue=None):
        Thread.__init__(self, log_queue=log_queue, name=name)
        self._halt = False
        self._master = master
        self._comm = comm
        if queue is not None:
            self.queue = queue

    def _run(self, key, request):
        try:
            reply = ""

            reply = "Got request [%s]. Thanks!" % str(request)
            self._log(reply)

            if request == "HALT":
                reply = "HALTING"
                self._halt = True
            else:
                cmd,proc = request.split('.')

            self._comm.reply(key, reply)

        except KeyboardInterrupt:
            pass
        except Exception, e:
            exc_type,exc_value,exc_traceback = sys.exc_info()
            self._log(traceback.format_exc(), 'err')

        if self._halt:
            self._log("halt requested")
            os.kill(os.getpid(), signal.SIGTERM)

    def halt_requested(self):
        return self._halt
#/*}}}*/

# === ProcessThread Class /*{{{*/
class ProcessThread(Thread):
    def __init__(self, master, comm, log_queue=None, name=None, queue=None):
        Thread.__init__(self, log_queue=log_queue, name=name)
        self._halt = False
        self._master = master
        self._comm = comm
        if queue is not None:
            self.queue = queue

    def _run(self, key, request):
        try:
            reply = ""

            reply = "Got request [%s]. Thanks!" % str(request)
            self._log(reply)

            if request == "HALT":
                reply = "HALTING"
                self._halt = True
            else:
                cmd,proc = request.split('.')

            self._comm.reply(key, reply)

        except KeyboardInterrupt:
            pass
        except Exception, e:
            exc_type,exc_value,exc_traceback = sys.exc_info()
            self._log(traceback.format_exc(), 'err')

        if self._halt:
            self._log("halt requested")
            os.kill(os.getpid(), signal.SIGTERM)

    def halt_requested(self):
        return self._halt
#/*}}}*/

# === Main Class /*{{{*/
class Main(Class):
    def __init__(self):
        Class.__init__(self)
        self.context = {'running' : False}
        signal.signal(signal.SIGTERM, self.halt_now)
        self.context['log'] = LogThread(prefix='processes_', note='PROCESSES', pid=True)
        self.context['log'].start()
        self.log_queue = self.context['log'].queue
        self.already_running = False
        # INFO: Can use the self._log() method after this point only  

    def usage(self, message=''):
        if message != '':
            print "E:", message
        self.parser.print_help()
        sys.exit(1)

    def error(self, message):
        print "E:", message
        sys.exit(1)

    def start(self):
        try:
            use_message = """usage: %prog [options]"""
            option_list = []
            option_list.append(optparse.make_option("-c", "--config-file", dest="config_file", action="store", help="config file for the process manager (usually processes.config)"))
            option_list.append(optparse.make_option("-p", "--process-file", dest="process_file", action="store", help="list of processes to manage (usually processes.list)"))
            parser = optparse.OptionParser(option_list=option_list, usage=use_message)
            options, args = parser.parse_args()

            config_file = "processes.config"
            process_file = "processes.list"

            if options.config_file:
                config_file = options.config_file
            if options.process_file:
                process_file = options.process_file

            print "Config file: %s" % config_file
            print "Process file: %s" % config_file

            config = Config.parse(config_file)
            processes = Config.parse(process_file)

            log_path = ''
            try: # Check for log directory
                log_path = os.path.abspath(config['log-path'])
                #self._log("log directory is '%s'" % log_path)
            except Exception, e:
                self._log("Config [log]:> %s" % (str(e),))

            if not os.path.exists(log_path):
                log_path = '.'

            self.context['log'].logger.set_log_path(log_path)

            #self._log("Config file is '%s'" % (config_file,))
            #self._log("Config contents: %s" % (str(config),))

            try: # Check for screen logging
                if config['log-to-screen'].lower() == 'true':
                    self.context['log'].logger.set_log_to_screen(True)
                    str_screen_logging = "Enabled"
                else:
                    self.context['log'].logger.set_log_to_screen(False)
                    str_screen_logging = "Disabled"
            except Exception, e:
                self._log("Config [log-to-screen]:> %s" % (str(e),))

            try: # Check for file logging
                if config['log-to-file'].lower() == 'true':
                    self.context['log'].logger.set_log_to_file(True)
                    str_file_logging = "Enabled"
                else:
                    self.context['log'].logger.set_log_to_file(False)
                    str_file_logging = "Disabled"
            except Exception, e:
                self._log("Config [log-to-file]:> %s" % (str(e),))

            try: # Check for debug logging
                if config['log-debug'].lower() == 'true':
                    self.context['log'].logger.set_log_debug(True)
                    str_debug_logging = "Enabled"
                else:
                    self.context['log'].logger.set_log_debug(False)
                    str_debug_logging = "Disabled"
            except Exception, e:
                self._log("Config [log-debug]:> %s" % (str(e),))

            # Check for processes already writing to this location.
            running = False
            pid_file = os.path.abspath("/tmp/processes.pid")
            if os.path.isfile(pid_file):
                tpid = open(pid_file, 'r').read(32).strip()
                ipid = -1
                try:
                    ipid = int(tpid)
                except:
                    pass
                if (ipid != os.getpid()) and find_proc(tpid):
                    restart_path = os.path.abspath("/tmp/restart.procsses.%s" % tpid)
                    running = True
                    if os.path.exists(restart_path):
                        if os.path.isfile(restart_path):
                            os.remove(restart_path)
                            kill_proc(tpid, log=self._log)
                            running = False
                        else:
                            self._log("Invalid type for restart file %s" % restart_path)
            if running:
                self._log("processes.py process [%s] is already running" % tpid)
                self.already_running = True
                raise KeyboardInterrupt

            self._log("=================")
            self._log("=== PROCESSES ===")
            self._log("=================")

            pid = os.getpid()
            self._log("starting processes.py [%d]" % pid)
            fh = open(pid_file, 'w+')
            fh.write('%s\n' % str(pid))
            fh.close()


            bind_port = 13131
            try: # Get control port
                port = int(config['bind-port'])
                if 0 < port < 65536:
                    bind_port = port
                else:
                    raise ValueError("Invalid port value.")
            except Exception, e:
                self._log("Config [bind-port]:> %s" % (str(e),))

            bind_ip = ''
            if config.has_key('bind-ip'):
                try: # Get LISS host
                    bind_ip = config['bind-ip']
                except Exception, e:
                    self._log("Config [bind-ip]:> %s" % (str(e),))

            print bind_ip, bind_port

            self.context['comm']    = CommThread(self, bind_port, bind_ip, log_queue=self.context['log'].queue)
            self.context['control'] = ControlThread(self, self.context['comm'].handler, log_queue=self.context['log'].queue, queue=self.context['comm'].handler._request_queue)


            #self._log("Listening on %s:%d" % self.context['comm'].handler.get_address())
            self._log("       Config file : %s" % (config_file,))
            self._log("     Log Directory : %s" % log_path)
            self._log("    Screen Logging : %s" % str_screen_logging)
            self._log("      File Logging : %s" % str_file_logging)
            self._log("     Debug Logging : %s" % str_debug_logging)

            self.context['control'].start()
            self.context['comm'].start()

            self.context['running'] = True

            self._log("----------------")
            self._log("--- Contexts ---")
            contexts = ['log','control','comm','running']
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

                if self.context['control'].halt_requested():
                    self._log("halt requested")
                    self.halt()
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
        thread_list = ['comm', 'control', 'log']
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

if __name__ == '__main__':
    try:
        Main().start()
    except KeyboardInterrupt:
        print

