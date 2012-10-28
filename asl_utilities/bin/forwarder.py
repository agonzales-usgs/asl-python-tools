#!/usr/bin/env python
import asl

from jtk import pxssh
from jtk.Class import Class
from jtk.Logger import LogThread
from jtk.Thread import Thread

import os
import string
import sys
import threading
import time
import traceback

def die(error_message=None, print_traceback=False, exit_code=1):
    if error_message is not None:
        sys.stderr.write(error_message)
    if print_traceback:
        (exc_type,exc_value,exc_trace) = sys.exc_info()
        traceback.print_tb(exc_trace)
        #sys.stderr.write(traceback.format_exc())
    sys.exit(exit_code)

# === Process Management Functions === #/*{{{*/
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

# === Configuration Parsing === #/*{{{*/
class ConfigNotFoundException(Exception):
    pass
class ConfigReadError(Exception):
    pass

def parse_config(config_file):
    config = {}
    forward = []
    reverse = []
    if not os.path.exists(config_file):
        raise ConfigNotFoundException("config path '%s' does not exist" % config_file)
    if not os.path.isfile(config_file):
        raise ConfigNotAFileException("config path '%s' is not a regular file" % config_file)
    try:
        lines = open(config_file, 'r').readlines()
        line_index = 0
        for line in map(string.strip, lines):
            line_index += 1
            if len(line) == 0:
                continue
            if line[0] == '#':
                continue
            parts = map(lambda p: p.strip().lower(), line.split('='))
            if len(parts) != 2:
                raise InvalidConfigException("bad entry on line %d" % line_index)
            key,value = parts
            if key in ('foward','reverse'):
                if not config.has_key(key):
                    config[key] = []
                config[key].append(value)
            else:
                if config.has_key(key):
                    raise InvalidConfigException("duplicate entry on line %d" % line_index)
                config[key] = value
    except:
        raise ConfigReadError("could not read config file '%s'" % config_file)

    return config
#/*}}}*/

# === Proxy Example Code === # /*{{{*/
    def construct(self):
        try:
            self.tunnel_ready = False
            attempts = 10 
            attempt  = 0
            while (not self.tunnel_ready) and ((attempts - attempt) > 0):
                self.halt_check()
                attempt += 1
                random.seed()
                if self.local_port is None:
                    self.local_port = random.randint(10001, 65001)
                bind_address = ""
                if self.local_address is not None:
                    bind_address = self.local_address + ":"
                if self.station_port == None:
                    self.station_port = 22
                self._log("bind_address    = %s" % str(bind_address))
                self._log("local_port      = %s" % str(self.local_port))
                self._log("station_address = %s" % str(self.station_address))
                self._log("station_port    = %s" % str(self.station_port))
                if not self.socks_tunnel:
                    tunnel_command = "-L%s%s:%s:%s" % (bind_address, str(self.local_port), self.station_address, str(self.station_port))
                else:
                    tunnel_command = "-D%s%s" % (bind_address, str(self.local_port))

                self._log("Proxy forwarding attempt #%d: %s" % (attempt, tunnel_command))

                self.halt_check()
                self._log("opening SSH command line...")

                self.reader.sendline()
                escape = ""
                for i in range(0, self.depth):
                    escape += '~'
                self.reader.send(escape + "C")
                try:
                    self.reader.expect("ssh>", timeout=10)
                except Exception, e:
                    self._log("Could not open SSH command interface: %s" % str(e))
                    response = self.reader.before
                    caught   = self.reader.after
                    self._log("  before: %s" % str(response))
                    self._log("  after:  %s" % str(caught))
                    continue
                response = self.reader.before
                caught   = self.reader.after

                self._log("before: %s" % response)
                self._log("after:  %s" % caught)

                self.halt_check()
                self._log("sending port forward command...")
                self.reader.sendline(tunnel_command)
                try:
                    self.reader.expect("Forwarding port.", timeout=10)
                    #if not self.reader.prompt(timeout=10):
                    #    raise ExTimeout("timeout on port forwarding operation.")
                except Exception, e:
                    self._log("No port forwarding feedback: %s" % str(e))
                    self._log("before: %s" % self.reader.before)
                    self._log("after:  %s" % self.reader.after)
                    continue
                response = self.reader.before
                caught   = self.reader.after

                self._log("before: %s" % response)
                self._log("after:  %s" % caught)

                self.halt_check()
                if re.compile("channel_setup_fwd_listener: cannot listen to port: %s" % str(self.local_port)).search(response):
                    self._log("Forwarding attempt #%d failed." % attempt)
                    continue

                self._log("Proxy forwarding tunnel established on port %s." % str(self.local_port))
                self.tunnel_ready = True

        except ExHaltRequest, e:
            self._log("Received a halt request, halting proxy connection attempt.")
        except Exception, e:
            self._log("Caught unexpected exception while attempting to open proxy tunnel.\n Exception: %s" % str(e))

        self.proxy_connect_lock.release()
        if not self.tunnel_ready:
            raise ExConnectFailed("Failed to set up proxy connection: %s" % str(e))
    
    def cleanup(self):
        try:
            self.proxy_connect_lock.release()
        except:
            pass

    def proxy_loop(self):
        self.running = True
        while self.running:
            try:
                self.reader.sendline()
                try:
                    self.reader.prompt( timeout=10 )
                except Exception, e:
                    pass
                response = self.reader.before
                self.halt_check(300)
            except ExHaltRequest, e:
                self._log("Received a halt request, terminating proxy connection.")
                self.running = False
# === END Proxy Example Code === # /*}}}*/


class Host:
    def __init__(self, host, port):
        self.host = host
        self.ip = socket.gethostbyname(host)
        self.port = int(port)

    def get_port(self):
        return self.port

    def get_hostname(self):
        return self.host
        
    def get_address(self):
        return (self.ip, self.port)

    def get_address_string(self):
        return str(self)

    def __repr__(self):
        return "%s:%d" % (self.ip, self.port)

class Forward:
    def __init__(self, proxy, remote, local, reverse=False):
        self.proxy  = proxy
        self.remote = remote
        self.local  = local
        self.reverse = reverse

    def get_forward_string(self):
        return "%s:%s" % (str(self.local), str(self.remote))


class Forwarder(Class):
    def __init__(self):
        Class.__init__(self, None)

        self.log_dir = "%(HOME)s/logs" % os.environ
        self.log_thread = LogThread(directory=self.log_dir, prefix="forwarder", note="Forwarder", name="LogThread")
        self.log_thread.start()

        self.log_queue = self.log_thread.queue
        self.log = self._log # log method

        self.delay = 60 # seconds
        self.host = "10.0.0.222"
        self.port = 22  
        self.username = "forward"
        self.password = "F0rw@rd3r!"

        self.forwards = [
            {   "reverse" : False,
                "proxy"   : ("10.0.0.222", 22),
                "bind"    : ("127.0.0.1", 2222),
                "target"  : ("127.0.0.1", 22),
            },
            {   "reverse" : True,
                "proxy"   : ("10.0.0.222", 22),
                "bind"    : ("127.0.0.1", 2222),
                "target"  : ("127.0.0.1", 22),
            },
        ]

    def run(self):
        try:
            while 1:

#pxssh.pxssh()
#  .login(
#       address,
#       username,
#       password=,
#       original_prompt=,
#       login_timeout=,
#       port=,
#       quiet=,
#       sync_multiplier=,
#       check_local_ip=
#   )
#
                self.conn = pxssh.pxssh()
                self.log("Connectiong to %s:%d ..." % (self.host,self.port))
                self.conn.login(self.host, self.username, password=self.password, port=self.port)
                self.log("Connected.")

                self.conn.sendline("ls")
                self.conn.prompt()
                self.log("Proof:" + self.conn.before)

                self.log("Adding forwards:")
                self.log("  Testing, so nothing yet.")
                self.log("All forwards added.")

                self.log("Connected. Entering the keep-alive loop ...")
                while open:
                    time.sleep(self.delay)
                    self.conn.sendline()
                    if not self.conn.prompt(timeout=5.0):
                        self.log("Connection to %s:%d dropped. Will re-open" % (self.host,self.port))
                        self.conn.logout()
                        break
                    self.log("Connection is up.")

        except KeyboardInterrupt:
            pass

        self.log_thread.halt()

if __name__ == "__main__":
    try:
        import psyco
        #psyco.full()
        psyco.profile()
        print "Psyco JIT enabled."
    except ImportError:
        pass

    Forwarder().run()
    #main()

