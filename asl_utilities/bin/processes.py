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
from jtk.Logger import LogThread
from jtk.StatefulClass import StatefulClass
from jtk.Thread import Thread
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

def kill_process(name, arg_list, log=print_func, tries=15, delay=1.0, interrupt=None):
    pid = find_process(arg_list)
    if pid is not None:
        log("sending SIGTERM to '%s' process [%s]" % (name,pid))
        os.kill(int(pid), 15)
        while 1 and ((interrupt is None) or (interrupt['stop'] == False)):
            tpid = not find_process(arg_list)
            if tpid != pid:
                log("'%s' process [%s] has died" % (name,pid))
                break
            tries -= 1
            if tries <= 0:
                log("sending SIGKILL to '%s' process [%s]" % (name,pid))
                os.kill(int(pid), 9)
                break
            time.sleep(delay)


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
    def __init__(self, master, comm, config, log_queue=None, name=None, queue=None):
        Thread.__init__(self, log_queue=log_queue, name=name, queue=queue)
        self._halt = False
        self._master = master
        self._comm = comm
        self._config = config
        self._processes = {}

    def add_process(self, id, args):
        self._processes[id] = ProcessThread(self, self._config, id, args)

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
                if not self._processes.has_key(proc):
                    reply = "Process '%s' not found"
                else:
                    process = self._processes[proc]
                    if cmd == "STATUS":
                        reply = process._state
                    elif cmd == "RESTART":
                        reply = process.queue.put((cmd, None))
                        reply = "Restarting '%s'" % proc
                    elif cmd == "ENABLE":
                        reply = process.queue.put((cmd, None))
                        reply = "Enabling '%s'" % proc
                    elif cmd == "DISABLE":
                        reply = process.queue.put((cmd, None))
                        reply = "Disabling '%s'" % proc
                    else:
                        reply = "Invalid Command" % cmd

            self._log(reply, 'dbg')
            self._comm.reply(key, reply)

        except KeyboardInterrupt:
            pass
        except Exception, e:
            exc_type,exc_value,exc_traceback = sys.exc_info()
            self._log(traceback.format_exc(), 'err')

        if self._halt:
            self._log("halt requested")
            os.kill(os.getpid(), signal.SIGTERM)

    def _post(self):
        for id in self._processes.keys():
            process = self._processes[id]
            del self._procsses[id]
            process.halt(join=True)

    def halt_requested(self):
        return self._halt
#/*}}}*/

# === ConfigThread Class /*{{{*/
class ConfigThread(Thread, StatefulClass):
    def __init__(self, master, db, log_queue=None, name=None):
        Thread.__init__(self, log_queue=log_queue, name=name)
        StatefulClass.__init__(self, db)
        self._master = master
        self.halt_now = self.halt # Must finish processing requests, or other threads will hang

    def _run(self, key, request):
        try:
            if key == "GET":
                k,_,q = request
                q.put(self.recall_value(k))
            elif key == "SET":
                k,v,q = request
                q.put(self.save_value(k,v))
        except KeyboardInterrupt:
            pass
        except Exception, e:
            exc_type,exc_value,exc_traceback = sys.exc_info()
            self._log(traceback.format_exc(), 'err')

    def get(self, key):
        queue = Queue.Queue()
        self.queue.put('GET', (key, None, queue))
        return queue.get()

    def set(self, key, value):
        queue = Queue.Queue()
        self.queue.put_nowait('SET', (key, value, queue))
        return queue.get()
#/*}}}*/

# === ProcessThread Class /*{{{*/
class ProcessThread(Thread):
    def __init__(self, master, config, id, args, log_queue=None, name=None):
        # wakeup every minute to ensure process is in the expected state
        Thread.__init__(self, log_queue=log_queue, name=name, timeout=60.0)
        self._master = master
        self._config = config
        self._id = id
        self._args = args
        self._state = "DISABLED"
        self._interrupt = {"stop": False}

    def _pre(self):
        self._state = self._config.get(self._id+"-STATE")

    def _run(self, cmd, data):
        try:
            if cmd == "DISABLE":
                self._state = "DISABLED"
                self._config.set(self._id+"-STATE", self._state)
            elif cmd == "ENABLE":
                self._state = "ENABLED"
                self._config.set(self._id+"-STATE", self._state)

            if cmd == "RESTART":
                if self._state == "ENABLED":
                    self._restart_process()
            elif self._state == "ENABLED": 
                self._start_process()
            elif self._state == "DISABLED": 
                self._kill_process()

        except KeyboardInterrupt:
            pass
        except Exception, e:
            exc_type,exc_value,exc_traceback = sys.exc_info()
            self._log(traceback.format_exc(), 'err')

    def _start_process(self):
        pid = find_process(self._args)
        if pid is not None:
            self._log("Process '%s' already running [%s] `%s`" % (self._id, pid, ' '.join(self._args)))
        else:
            os.spawnv(os.P_NOWAIT, self._args[0], self._args)

            check_interval = 0.25
            remaining_checks = 20
            while remaining_checks > 0:
                pid = find_process(self._args)
                if pid is not None:
                    remaining_checks = 0
                else:
                    remaining_checks -= 1
                    sys.stdout.write(".")
                    sys.stdout.flush()
                    time.sleep(check_interval)
            sys.stdout.write("\n")

            if pid is not None:
                self._log("Spawned process '%s' [%s] `%s`" % (self._id, pid, ' '.join(self._args)))
            else:
                self._log("Process '%s' did not start" % self._id, 'warn')

    def halt_now(self, join=True):
        self._interrupt["stop"] = True
        Thread.halt_now(self, join)

    def _restart_process(self):
        self._kill_process()
        self._start_process()

    def _kill_process(self):
        kill_process(self._id, self._args, self._log, tries=30, delay=1.0, interrupt=self._interrupt)
#/*}}}*/

# === Main Class /*{{{*/
class Main(Class):
    def __init__(self):
        Class.__init__(self)
        signal.signal(signal.SIGTERM, self.halt_now)

        self.running = False
        self.threads = {}
        self.thread_order = []

        self.add_thread('log', LogThread(prefix='processes_', note='PROCESSES', pid=True))
        self.t('log').start()
        self.log_queue = self.t('log').queue

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

    def add_thread(self, id, thread):
        self.threads[id] = thread
        self.thread_order.append(id)

    def t(self, id):
        return self.threads[id]

    def start(self):
        try:
            use_message = """usage: %prog [options]"""
            option_list = []
            option_list.append(optparse.make_option("-c", "--config-file", dest="config_file", action="store", help="config file for the process manager"))
            option_list.append(optparse.make_option("-p", "--process-file", dest="process_file", action="store", help="list of processes to manage"))
            option_list.append(optparse.make_option("-s", "--state-database", dest="state_database", action="store", help="process state configurations"))
            parser = optparse.OptionParser(option_list=option_list, usage=use_message)
            options, args = parser.parse_args()

            config_file = "processes.config"
            process_file = "processes.list"
            state_db = ".processes.sqlite"
            if os.environ.has_key("HOME"):
                state_db = "%s/%s" % (os.environ["HOME"], state_db)

            if options.config_file:
                config_file = options.config_file
            if options.process_file:
                process_file = options.process_file
            if options.state_database:
                state_db = options.state_database

            print "Config file: %s" % config_file
            print "Process file: %s" % config_file
            print "State database: %s" % state_db

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

            self.t('log').logger.set_log_path(log_path)

            #self._log("Config file is '%s'" % (config_file,))
            #self._log("Config contents: %s" % (str(config),))

            try: # Check for screen logging
                if config['log-to-screen'].lower() == 'true':
                    self.t('log').logger.set_log_to_screen(True)
                    str_screen_logging = "Enabled"
                else:
                    self.t('log').logger.set_log_to_screen(False)
                    str_screen_logging = "Disabled"
            except Exception, e:
                self._log("Config [log-to-screen]:> %s" % (str(e),))

            try: # Check for file logging
                if config['log-to-file'].lower() == 'true':
                    self.t('log').logger.set_log_to_file(True)
                    str_file_logging = "Enabled"
                else:
                    self.t('log').logger.set_log_to_file(False)
                    str_file_logging = "Disabled"
            except Exception, e:
                self._log("Config [log-to-file]:> %s" % (str(e),))

            try: # Check for debug logging
                if config['log-debug'].lower() == 'true':
                    self.t('log').logger.set_log_debug(True)
                    str_debug_logging = "Enabled"
                else:
                    self.t('log').logger.set_log_debug(False)
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

            self.add_thread('config', ConfigThread(self, state_db))
            comm_thread = CommThread(self, bind_port, bind_ip, log_queue=self.t('log').queue)
            self.add_thread('control', ControlThread(self, comm_thread.handler, self.t('config'), log_queue=self.t('log').queue, queue=comm_thread.handler._request_queue))
            self.add_thread('comm', comm_thread)

            #self._log("Listening on %s:%d" % self.t('comm').handler.get_address())
            self._log("       Config file : %s" % config_file)
            self._log("    State Database : %s" % state_db)
            self._log("     Log Directory : %s" % log_path)
            self._log("    Screen Logging : %s" % str_screen_logging)
            self._log("      File Logging : %s" % str_file_logging)
            self._log("     Debug Logging : %s" % str_debug_logging)

            for thread_id in self.thread_order:
                thread = self.t(thread_id)
                if not thread.isAlive():
                    thread.start()

            self.running = True

            self._log("----------------")
            self._log("--- Threads ---")
            max_id = max(map(len, self.thread_order))
            for thread_id in self.thread_order:
                thread = self.t(thread_id)
                self._log("  %s : %s (%s)" % (thread_id.rjust(max_id), thread.name, T(thread.isAlive(),"Running","Halted")))

            while self.running:
                try: 
                    signal.pause()
                    self._log("caught a signal")
                except:
                    time.sleep(1.0)

                if self.thread['control'].halt_requested():
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
        for thread_id in self.thread_order[::-1]:
            if not self.already_running:
                self._log("halting %s..." % self.t(thread_id).name)
            if thread_id and self.t(thread_id).isAlive():
                if now:
                    self.t(thread_id).halt_now()
                else:
                    self.t(thread_id).halt()
                self.t(thread_id).join()
        self.running = False

    def halt_now(self, signal=None, frame=None):
        self.halt(True)
#/*}}}*/

if __name__ == '__main__':
    try:
        Main().start()
    except KeyboardInterrupt:
        print

