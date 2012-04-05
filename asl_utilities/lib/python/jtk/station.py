"""
This module provides automated debugging and software upgrade 
tools for various stations
Station680 (Under Development): for debugging our Q680 stations
StationSlate (Completed): for debugging and upgrading our Q330 stations

Expansion: Eventually I would like to modify this class to provide
           individual functions for each stage of the debug. The
           barriers I am seeing are due to limitations in pexpect,
           where 'before' is not available until after the next
           sendline() has been issued. Perhaps a modification of
           this module is feasible.

           Also, instead of pre-defined return types, I intened
           to introduce exceptions to describe the various errors
           one can encounter.
"""

try:
    import datetime # to manage time differences
    import pexpect  # expect lib
    import pxssh    # ssh extension to pexepect
    import re       # regular expression parser
    import os       # file operations
    import Queue    # thread-safe communication queue
    import random   # random number generation
    import stat     # file modes
    import sys      # arguments
    import time     # to get UTC current time
    import thread   # provides a lock
    import threading
    import traceback

    from disconnects import DisconnectParser
    from Logger import Logger
    from permissions import Permissions
    import dlc
    import hashsum
except ImportError, e:
    raise ImportError (str(e) + """
A critical module was not found. 
Python 2.4 is the minimum recommended version.
You will need modules 'pexpect' and 'pxssh'.
""")


# === Exception Classes/*{{{*/
"""Parent of all exception classes in the station module"""
class ExceptionStation(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return str(self.value)
    def get_trace(self):
        """This returns an abbreviated stack trace with lines that 
           only concern the caller."""
        tblist = traceback.extract_tb(sys.exc_info()[2])
        tblist = filter(self.__filter_not_pexpect, tblist)
        tblist = traceback.format_list(tblist)
        return ''.join(tblist)
    def __filter_not_pexpect(self, trace_list_item):
        if trace_list_item[0].find('stations.py') == -1:
            return True
        else:
            return False

class ExHaltRequest(ExceptionStation):
    """Raised when a request has been sent to halt a station thread."""

class ExTimeout(ExceptionStation):
    """Raised when a station conneciton times out."""

class ExIncomplete(ExceptionStation):
    """Raised when connection info is incomplete."""

class ExLaunchFailed(ExceptionStation):
    """Raised when the application failed to launch."""
class ExConnectFailed(ExceptionStation):
    """Raised when connection can not be established."""
class ExDisconnectFailed(ExceptionStation):
    """Raised when connection can not be established."""
class ExInvalidCredentials(ExceptionStation):
    """Raised when username or password is invalid."""

class ExUnrecognizedPubKey(ExceptionStation):
    """Raised when an incorrect public key is received while
       attempting to open an ssh connection."""
class ExProtocolUnrecognized(ExceptionStation):
    """Raised when the selected protocol is not recognized
       by the station class."""
class ExNoReader(ExceptionStation):
    """Raised when communication is envoked before reader 
       is initialized."""
class ExNotConnected(ExceptionStation):
    """Raised when attempting to communicated with a station 
       before the connection has been established."""

class ExStationTypeNotRecognized(ExceptionStation):
    """Raised when the station type is not recognized"""
class ExStationNotSupported(ExceptionStation):
    """Raised when the station type is not recognized"""
class ExStationDisabled(ExceptionStation):
    """Raised when the station is disabled"""

class ExProxyTypeNotRecognized(ExceptionStation):
    """Raised when the proxy type is not recognized"""

# === Exception Classes (END)/*}}}*/

# === Station Class/*{{{*/
class Station(threading.Thread):
    def __init__(self, name, action, loop_queue=None):
        threading.Thread.__init__(self, name=name)

        self.loop_queue = loop_queue
        self.running = False
        self.halt_request = False

        # timeouts
        self.spawn_timeout    = 5
        self.comm_timeout     = 900 # was 1800, but this is better for re-tries
        self.check_timeout    = self.comm_timeout
        self.parse_timeout    = self.comm_timeout
        self.search_timeout   = self.comm_timeout * 2
        self.transfer_timeout = self.comm_timeout * 2
        self.launch_timeout   = self.comm_timeout
        self.sync_multiplier  = 10  # determines how long pxssh prompt sync should take

        self.start_time = None

        self.name     = name
        self.type     = None
        self.group    = None
        self.address  = None
        self.port     = None
        self.username = None
        self.password = None
        self.ssh_options = None

        self.info       = {}
        self.proxy      = None
        self.proxy_info = None

        self.action = action

        self.com_app   = None
        self.protocol  = None
        self.connected = False

        # expected prompts
        self.prompt_pass  = None
        self.prompt_user  = None
        self.prompt_shell = None

        self.verbosity = 3
        self.reader = None

        # new logging mechanism
        self.logger = Logger()
        self.logger.set_log_to_screen(False)
        self.parser = DisconnectParser()

        self.output_directory = ""
        self.summary = ""

    def _log(self, str, category="info"):
        if category == "":
            self.logger.log( str )
        else:
            self.logger.log( str, category )

    def log_file_name(self, name=""):
        if name != "":
            self.logger.set_log_file( name )
        return self.logger.get_log_file()

    def log_path_name(self, path=""):
        if path != "":
            self.logger.set_log_path( path )
        return self.logger.get_log_path()

    def log_to_file(self, to_file=True):
        self.logger.set_log_to_file( to_file )

    def log_to_screen(self, to_screen=True):
        self.logger.set_log_to_screen( to_screen )

    def set_output_directory(self, directory):
        if os.path.isdir(directory):
            self.output_directory = directory

    def halt(self, now=False):
        self._halt(now)

    def _halt(self, now):
        if self.reader:
            self.reader.close()
        raise ExhaltRequest("Halt Now")

    def is_done(self):
        alive = False
        try:
            alive = self.is_alive()
        except:
            alive = self.isAlive()
        return not alive

    def run(self):
        self.running = True
        try:
            if self.proxy is not None:
                self._log("Waiting for proxy to start...")
                if self.proxy.wait_for_ready() == False:
                    raise ExConnectFailed("Could not establish proxy connection to '%s' for station '%s' " % (self.proxy.name, self.name))
                self.start_time = time.mktime(time.gmtime())
                self._log("Proxy connection established.")
            if self.action == 'check':
                self.run_check()
            elif self.action == 'run':
                self.run_commands()
            elif self.action == 'update':
                self.run_update()
            elif self.action == 'proxy':
                self.run_proxy()
            else:
                self._log("Invalid action for station(s): '%s'" % action)
        except ExHaltRequest, e:
            self._log( "Halt Command Received", "info" )
            #(ex_f, ex_s, trace) = sys.exc_info()
            #traceback.print_tb(trace)
        except Exception, e:
            self._log( "Station::run() caught exception: %s" % str(e), "error" )
            (ex_f, ex_s, trace) = sys.exc_info()
            traceback.print_tb(trace)

        # Give child classes an opportunity to clean things up,
        # even after a severe error. This is essential for proxies
        # that fail to successfully connect, as there are dependent
        # processes waiting on the completion of thier initialization.
        self.cleanup()

        try:
            if self.proxy is not None:
                self._log("requesting proxy halt")
                self.proxy.halt()
                self.proxy.join()
        except Exception, e:
            self._log( "Station::run() caught exception: %s" % str(e), "error" )
            (ex_f, ex_s, trace) = sys.exc_info()
            traceback.print_tb(trace)

        self.running = False
        if self.loop_queue is not None:
            self.loop_queue.put(('DONE', self))

    def run_commands(self):
        self.ready()
        self.connect()
        self.process_commands(self.commands)
        self.disconnect()

    def run_check(self):
        self.ready()
        self.connect()
        self.check()
        self.disconnect()

    def run_update(self):
        self.ready()
        self.connect()
        self.check_software_versions()
        self.transfer()
        self.update()
        self.disconnect()

    def run_proxy(self):
        self.ready()
        self.connect()
        self.construct()
        self.proxy_loop()
        self.disconnect()

    def cleanup(self):
        pass

    def check(self):
        self._log( "Station::check() this method must be overriden. Throwing a fit!!" , "error" )
        raise Exception, "Station::check() this function must be overriden."

    def transfer(self):
        self._log( "Station::transfer() this method must be overriden. Throwing a fit!!" , "error" )
        raise Exception, "Station::transfer() this function must be overriden."

    def update(self):
        self._log( "Station::check() this method must be overriden. Throwing a fit!!" , "error" )
        raise Exception, "Station::check() this function must be overriden."

    def min_info(self):
        if self.name and self.username and self.password:
            return 1
        return 0

    def set_group(self, group):
        self.group = group

    def set_name(self, name):
        self.name = name
        self.logger.set_log_note( self.name )

    def set_address(self, address):
        self.address = address

    def set_port(self, port):
        self.port = port

    def set_username(self, username):
        self.username = username

    def set_password(self, password):
        self.password = password

    def set_com_app(self, com_app):
        self.com_app = com_app 

    def ready(self):
        if self.name == "":
            self.name = "anonamous"
        if (self.address is None) or (self.address == ""):
            raise ExIncomplete, "Server address not specified"
        if (self.username is None) or (self.username == ""):
            raise ExIncomplete, "Username not specified"
        if (self.password is None) or (self.password == ""):
            raise ExIncomplete, "Password not specified"
        if (self.proxy is not None) and (self.proxy.connected):
            self._log("updating station with proxy info")
            self.address = self.proxy.local_address
            self.port = self.proxy.local_port
            self._log("proxy address = %s" % str(self.address))
            self._log("proxy port    = %s" % str(self.port))

    def connect(self):
        if self.protocol == "qdp":
            pass
        elif self.protocol == "telnet":
            self.telnet_connect()
        elif self.protocol == "ssh":
            self.ssh_connect()
        else:
            raise ExProtocolUnknown, "The chosen protocol is not supported"
        self.connected = True

    def disconnect(self):
        if (self.protocol != "qdp") and (not self.reader):
            raise ExNotConnected, "There was no connection established"

        if self.protocol == "qdp":
            pass
        elif self.protocol == "telnet":
            self.telnet_disconnect()
        elif self.protocol == "ssh":
            self.ssh_disconnect()
        else:
            raise ExProtocolUnknown, "The chosen protocol is not supported"
        self.connected = False

    def telnet_connect(self):
        # spawn the telnet program
        self.reader = pexpect.spawn( self.com_app )
        try:
            self._log( "launching telnet" )
            self._log( "telnet spawn timeout: %d" % self.spawn_timeout )
            self.reader.expect( "telnet> ", timeout=self.spawn_timeout )
        except Exception, e:
            self._log( "exception details: %s" % str(e) )
            raise ExLaunchFailed, "Failed to spawn telnet"

        # open telnet connection to station
        server = self.address 
        if ( self.port ):
            server += " " + str(self.port)
        self.reader.sendline( "open " + server )
        try:
            self._log( "opening connection to station" )
            match = self.reader.expect( [self.prompt_user], timeout=self.comm_timeout )
        except Exception, e:
            (ex_f, ex_s, trace) = sys.exc_info()
            traceback.print_tb(trace)
            raise ExConnectFailed, "Unable to telnet to station " + self.address

        # enter the username
        self.reader.sendline( self.username )
        try:
            self._log( "supplying username" )
            self.reader.expect( [self.prompt_pass], timeout=self.comm_timeout )
        except:
            raise ExInvalidCredentials, "Invalid Username or Password"

        # enter the password
        self.reader.sendline( self.password )
        try:
            self._log( "supplying password" )
            self.reader.expect( ['SUPER:','Super:','sysop:'], timeout=self.comm_timeout )
        except:
            raise ExInvalidCredentials, "Invalid Username or Password"

    def telnet_disconnect(self):
        try:
            self.reader.sendline( "logout" )
            self.reader.expect( pexpect.EOF, timeout=self.comm_timeout )
            self._log( "closing telnet connection..." )
        except Exception, e:
            #self._log( "Station::telnet_disconnect() caught exception while trying to close telnet connection: %s" % e.__str__() )
            raise ExDisconnectFailed, "Disconnect Failed: " % str(e)

    def ssh_connect(self):
        try:
            self._log( "creating pxssh reader object" )
            self.reader = pxssh.pxssh()
        except Exception, e:
            self._log( "exception details: %s" % str(e) )
            raise ExLaunchFailed, "Failed to spawn ssh process"

        try:
            prompt = "[$#>]"
            quiet  = True
            check_local_ip = True
            if self.info['type'] == 'Proxy':
                prompt = "[$>]"
                quiet  = False
            if self.proxy is not None:
                check_local_ip = False
            if self.prompt_shell is not None:
                prompt = self.prompt_shell
            self._log("opening ssh connection")
            self._log("address:  %s" % self.address)
            self._log("port:     %s" % str(self.port))
            self._log("username: %s" % self.username)
            self._log("sync-multiplier: %s" % str(self.sync_multiplier))
            try:
                pass_len = len(self.password)
            except:
                pass_len = 0
            self._log("password: *** [%d]" % pass_len)
            self._log("prompt:   %s" % prompt)
            self.reader.login(self.address, self.username, password=self.password, original_prompt=prompt, login_timeout=self.comm_timeout, port=self.port, quiet=quiet, sync_multiplier=self.sync_multiplier, check_local_ip=check_local_ip)
        except Exception, e:
            self._log("reader.before: %s" % self.reader.before)
            self._log("exception details: %s" % str(e))
            (ex_f, ex_s, trace) = sys.exc_info()
            traceback.print_tb(trace)
            raise ExConnectFailed, "Failed to ssh to station: %s" % str(e)

    def ssh_disconnect(self):
        try:
            self._log( "closing ssh connection..." )
            self.reader.logout()
        except Exception, e:
            self._log( "Station::ssh_disconnect() caught exception while trying to close ssh connection: %s" % e.__str__(), "error" )
            raise ExDisconnectFailed, "Disconnect Failed: %s" % str(e)

# === Station Class (END)/*}}}*/

# === Proxy Class/*{{{*/
class Proxy(Station):
    def __init__(self, name, socks_tunnel=False, log_queue=None):
        Station.__init__(self, name, 'proxy')

        self.depth = 1

        self.prompt_pass = ""
        self.protocol = "ssh"
        self.socks_tunnel = socks_tunnel
        self.socks_port = None

        self.output = ""
        self.log_messages = ""
        self.summary = ""

        self.queue = Queue.Queue()
        self.running = False

        self.log_queue = log_queue

        self.local_address = None
        self.local_port = None

        self.station_address = None
        self.station_port = None

        self.address = None
        self.port = None
        self.username = None
        self.password = None
        self.tunnel_ready = False

        # Create and acquire the lock now. This prevents
        # the parent thread (which is dependent on this
        # proxy) from checking too soon. Once this thread
        # has started, the lock is released, and the parent
        # is free to receive the connection confirmation.
        self.proxy_connect_lock = thread.allocate_lock()
        self.proxy_connect_lock.acquire(0)

    def _log(self, str, category="info"):
        if self.log_queue != None:
            message = [self.name, str]
            if category:
                message.append(category)
            self.log_queue.put(tuple(message))
        else:
            Station._log(self, str, category)
    
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

    def halt_proxy(self):
        self.queue.put('HALT')

    def halt_check(self, timeout=0):
        start = time.time()
        while timeout >= 0:
            try:
                request = self.queue.get(True, timeout)
                if request == 'HALT':
                    raise ExHaltRequest("HALT")
            except Queue.Empty:
                pass
            timeout = timeout - (time.time() - start)

    def _halt(self, now):
        self.halt_proxy()

    def wait_for_ready(self, timeout=None):
        self.proxy_connect_lock.acquire(1)
        self.proxy_connect_lock.release()
        return self.tunnel_ready

    def check(self):
        pass
# === Proxy Class (END)/*}}}*/

# === Station680 Class/*{{{*/
class Station680(Station):
    def __init__(self, name, action, loop_queue):
        Station.__init__(self, name, action, loop_queue)

        self.netservs = []
        self.servers  = []

        # prompts to expect
        self.com_app     = os.popen('which telnet').read().strip()
        self.prompt_user = "User name\?:"
        self.prompt_pass = "Password:"
        self.protocol    = "telnet"
        self.port = 23

        self.output = ""      # results of the checks script
        self.log_glance = ""  # quick glimpse at first 20 records
        self.log_span = 2500  # this will be adjusted if it is too short
        self.max_span = 25000 # don't search deeper than this 
        self.log_messages = ""

    def add_netserv_log(self, log_name):
        self._log( "adding netserv log: %(log)s" % {"log": log_name} )
        self.netservs.append(log_name)

    def add_server_log(self, log_name):
        self._log( "adding server log: %(log)s" % {"log": log_name} )
        self.servers.append(log_name)

    def ready(self):
        if len(self.netservs) < 1:
            self.netservs.append("netserv")
        if len(self.servers) < 1:
            self.servers.append("server")
        Station.ready(self)


    def reboot(self):
        self._log( "The reboot option is not supported yet." )
        pass


    def check(self):
        if not self.reader:
            raise ExNoReader, "Reader was not initialized"
        if not self.connected:
            raise ExNotConnected, "Not connected to station"

        # run the 'checks' script
        self._log( "running 'checks' script" )
        self.reader.sendline( "checks" )
        try:
            self.reader.expect( ['SUPER:','Super:','sysop:'], timeout=self.check_timeout )
        except:
            raise ExceptionStation, "Station680::check() checks did not complete"

        # request the contents of 'output'
        self._log( "getting checks output" )
        self.reader.sendline( "list output" )
        try:
            self.reader.expect( ['SUPER:','Super:','sysop:'], timeout=self.parse_timeout )
        except:
            raise ExceptionStation, "Station680::check() failed to list output"

        # Watch out, you can get the following error if
        # too many retrieve processes are running already
        #    "TOO MANY RETRIEVE USERS, TRY AGAIN LATER"
        #
        # We can catch this error, parse 'procs -a' output,
        # and kill excess processes. However, this is not
        # recommended, as we could be messing with other
        # users.

        # launch the retrieve program
        self._log( "launching retrieve" )
        self.reader.sendline( "retrieve -nl -nt -q=c" )
        self.output = self.reader.before # record contents of 'output'
        try:
            self.reader.expect( ['Command\?'], timeout=self.launch_timeout )
        except:
            raise ExceptionStation, "Station680::check() failed to launch retrieve"

        # initial log check
        self.reader.sendline( "yt " + str(self.log_span) + " 1" )
        try:
            self.reader.expect( ['Command\?'], timeout=self.parse_timeout )
        except:
            raise ExceptionStation, "Station680::check() initial log check failed"

        # create a value to compare against
        target_time = time.time() - 604800 # 1 week
        
        # loop here until sample is large enough
        while 1:
            self.reader.sendline( "yt " + str(self.log_span + 1000) + " 1" )
            date_chk_string = self.reader.before
            try:
                self.reader.expect( ['Command\?'], timeout=self.parse_timeout )
            except:
                raise ExceptionStation, "Station680::check() dropped out of log check loop, log_span=" + str(self.log_span)

            # parse and check if date goes back far enough,
            # loop until it does or until the max parse size
            regex = re.compile('(\d{4})\/(\d{2})\/(\d{2})')
            match = regex.search( date_chk_string, 0 )
            if not match:
                #raise ExceptionStation, "Station680::check() could not locate date"
                self.log_span -= 1000
                break
            if match.group() == "1900/00/00":
                this_time = 0
            else:
                this_time = time.mktime(time.strptime(match.group(), "%Y/%m/%d"))
            #print "Time Span:   " + str(self.log_span)
            #print "Time String: " + match.group()
            #print "Target time: " + str(target_time)
            #print "Actual time: " + str(this_time) + "\n"

            if (this_time <= target_time) or (self.log_span > self.max_span):
                break
            else:
                self.log_span += 1000

        # include a quick peak at the first 20 records
        self.reader.sendline( "yt" )
        try:
            self.reader.expect( ['Command\?'], timeout=self.parse_timeout )
        except:
            raise ExceptionStation, "Station680::check() log peak failed"

        # for each self.servers and self.netservs, grep logs
        for netserv in self.netservs:
            self._log( "scanning %(span)d records for %(log)s" % {"span": self.log_span, "log": netserv})
            self.reader.sendline( "yt *" + netserv + " " + str(self.log_span) )
            self.log_messages += self.reader.before
            try:
                self.reader.expect( ['Command\?'], timeout=self.parse_timeout )
            except:
                raise ExceptionStation, "Station680::check() failed to run netserv search for: " + netserv

        for server in self.servers:
            self._log( "scanning %(span)d records for %(log)s" % {"span": self.log_span, "log": server})
            self.reader.sendline( "yt *" + server + " " + str(self.log_span) )
            self.log_messages += self.reader.before
            try:
                self.reader.expect( ['Command\?'], timeout=self.parse_timeout )
            except:
                raise ExceptionStation, "Station680::check() failed to run server search for: " + server

        # Get a list of the segments available
        self._log( "getting available segments" )
        self.reader.sendline( "e" )
        self.log_messages += self.reader.before
        try:
            self.reader.expect( ['\?'], timeout=self.parse_timeout )
        except:
            raise ExceptionStation, "Station680::check() segment selection: open failed"

        self.reader.sendline( time.strftime("%y/%m/%d", time.gmtime()) )
        try:
            self.reader.expect( ['\?'], timeout=self.parse_timeout )
        except:
            raise ExceptionStation, "Station680::check() segment selection: "

        self.reader.sendline( "" )
        try:
            self.reader.expect( ['Command\?'], timeout=self.parse_timeout )
        except:
            raise ExceptionStation, "Station680::check() segment selection: "

        # Print a list of the instruments for this station
        self._log("printing instrument list")
        self.reader.sendline( "r" )
        self.log_messages += self.reader.before
        try:
            self.reader.expect( ['Command\?'], timeout=self.parse_timeout )
        except:
            raise ExceptionStation, "Station680::check() failed to print reference"

        # exit from retrieve
        self._log( "exiting retrieve" )
        self.reader.sendline( "q" )
        self.log_messages += self.reader.before
        try:
            self.reader.expect( ['SUPER:','Super:','sysop:'], timeout=self.comm_timeout )
        except:
            raise ExceptionStation, "Station680::check() failed to quit retrieve cleanly"
        #self.reader.sendline( "logout" )
        #self.reader.expect( pexpect.EOF, timeout=self.comm_timeout )

        self.build_summary()

    # This will build a summary of the information we evaluate
    # from the ouput of checks. 
    def build_summary(self, lines=None):

        if not lines:
            lines = self.output

        s_type    = "Q680-LOCAL"
        s_name    = self.name[3:]
        s_uptime  = 0
        s_outages = [] 

        # TODO:
        # We should now parse through the content of the 'output' file
        # and flag various warnings:
        # [ ]1. Look for 'Tape Status'
        #   [ ]a. record warning values on tapes (FULL, FAULT, HIDDEN)
        #   [ ]b. record percent for DATA=
        #   [ ]c. ensure DATA is <= 100%
        #   [ ]d. ensure DATA is increasing
        #   [ ]e. write to to chk file

        self.summary += "UTC Timestamp: %s\n" % time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

        # Calculate uptime
        regex = re.compile( "(\d{1,})[:]\d{2} sysgo" )
        match = regex.search( lines )
        if match:
            days = int( match.group(1) ) / 24
            message = "uptime: %d days" % days
            self._log( message )
            self.summary += message  + "\n"
            s_uptime = days

        # Check disk space (determine a good threshold)
        reg_disk_space = re.compile( "(\d{1,12}) of (\d{1,12}) bytes \(\d{1,10}[.]\d{2} of \d{1,10}[.]\d{2} Mb\) free on media" )
        disk_space_total = 0
        disk_space_free = 0
        matches = reg_disk_space.findall( lines )
        if matches:
            print matches[0]
            disk_space_total = int( matches[0][1] )
            disk_space_free  = int( matches[0][0] )
            disk_space_free_percent = (float(disk_space_free) / float(disk_space_total) * 100.0)
            message = "Free disk space: %.02f%%" % disk_space_free_percent
            self._log( message )
            self.summary += message + "\n"
        else:
            message = "Unable to located disk health stats."
            self._log( message )
            self.summary += message + "\n"

        # Check free RAM compared to available
        reg_ram_total = re.compile( "Total RAM at startup:\s+(\d{1,5})[.]\d{2}" )
        reg_ram_free = re.compile( "Current total free RAM:\s+(\d{1,5})[.]\d{2}" )

        ram_total = 0
        matches = reg_ram_total.findall( lines )
        if matches:
            ram_total = int( matches[0] )
        ram_free = 0
        matches = reg_ram_free.findall( lines )
        if matches:
            ram_free = int( matches[0] )

        if ram_total and ram_free:
            percent_free = float(ram_free) / float(ram_total) * 100.0
            message = "Free memory: %.02f%%" % percent_free
            self._log( message )
            self.summary += message + "\n"
        else:
            message = "Unable to locate memory stats."
            self._log( message )
            self.summary += message + "\n"

        # Check memory segmentation (extract segment count)
        reg_ram_segments = re.compile( "[$][0-9A-F]{1,8}\s+[$][0-9A-F]{1,8}\s+\d{1,5}[.]\d{2}" )
        matches = reg_ram_segments.findall( lines )
        if matches:
            segment_count = len( matches )
            message = "Found %d memory segments" % segment_count
            self._log( message )
            self.summary += message + "\n"
        else:
            message = "No memory segments found."
            self._log( message )
            self.summary += message + "\n"

        # Find memory modules
        reg_mem = re.compile( "(\s+|^)rxdat_(\d{1,3})(\s|$)" )
        matches = reg_mem.findall( lines )
        if matches:
            for match in matches:
                pid = int( match[1] )
                reg_pid = re.compile( "%d\s+\d{1,5}\s+\d{1,5}[.]\d{1,5}\s+\d{1,5}\s+\d{1,5}.\d{2}[km]\s+\d{1,5}\s+[wsae*-]\s+(?:(?:\d{1,5}[:])?\d{1,2}[:])?\d{1,2}.\d{2}\s+\d{1,5}[:]\d{2}\s+(\w+)" % pid )
                result = reg_pid.findall( lines )
                if result:
                    process = result[0]
                    message = "rxdat module pid: %(pid)d [%(proc)s]" % {"pid": pid, "proc": process }
                    self._log( message )
                    self.summary += message  + "\n"
                else:
                    message = "rxdat module pid: %d [none]" % pid
                    self._log( message )
                    self.summary += message + "\n"

        # Check connections (ftp and telnet)
        exp_address = "\d{1,3}[.]\d{1,3}[.]\d{1,3}[.]\d{1,3}"
        link_list = []
        proc_list = []

        reg_proc = re.compile( "(\d{1,5})\s+\d{1,5}\s+\d{1,5}[.]\d{1,5}\s+\d{1,5}\s+\d{1,5}.\d{2}[km]\s+\d{1,5}\s+[wsae*-]\s+(?:(?:\d{1,5}[:])?\d{1,2}[:])?\d{1,2}.\d{2}\s+(\d{1,5})[:](\d{2})\s+(ftpdc|telnetdc)" )
        reg_link = re.compile( "\d{1,5}\s+(\d{1,5})\s+tcp\s+%(local_ip)s[:](telnet|23|ftp|21)\s+(%(foreign_ip)s)[:]\d{1,5}\s+established" % {"local_ip": exp_address, "foreign_ip": exp_address} )

        matches = reg_proc.findall( lines )
        if matches:
            for match in matches:
                node = {}
                node['pid'] = int( match[0] )
                node['age'] = (int( match[1] ) * 60) + int( match[2] )
                node['type'] = match[3]
                proc_list.append( node )

        matches = reg_link.findall( lines )
        if matches:
            for match in matches:
                node = {}
                node['pid']  = int( match[0] ) 
                node['port'] = match[1]
                node['ip']   = match[2]
                link_list.append( node )

        for proc in proc_list:
            for link in link_list:
                if proc['pid'] == link['pid']:
                    pid  = proc['pid']
                    name = proc['type']
                    age  = proc['age']
                    ip   = link['ip']
                    message = "process %(name)s [%(pid)d] age %(age)d minutes, host %(host)s" % {"name": name, "pid": pid, "age": age, "host": ip}
                    self._log( message )
                    self.summary += message + "\n"

        # Find leftover retrieve processes 
        reg_proc = re.compile( "(\d{1,5})\s+\d{1,5}\s+\d{1,5}[.]\d{1,5}\s+\d{1,5}\s+\d{1,5}.\d{2}[km]\s+\d{1,5}\s+[wsae*-]\s+(?:(?:\d{1,5}[:])?\d{1,2}[:])?\d{1,2}.\d{2}\s+(\d{1,5})[:](\d{2})\s+(retrieve)" )

        matches = reg_proc.findall( lines )
        if matches:
            for match in matches:
                self._log( "found %(type)s process with pid %(pid)s" % {"type": match[3], "pid": match[0]} )

        # Check for packet delay from DAs
        reg_packet_delay = re.compile( "(\w+) Comlink Status.*?\r\n(?:[^ ][^\r\n]+?\r\n)*?([-]?\d{1,10}) seconds since last good packet received[.]", re.M )
        packet_delay = 0 # seconds since last good packet received
        matches = reg_packet_delay.findall( lines )
        if matches:
            for match in matches:
                comlink_name = match[0]
                delay = int( match[1] )
                message = "%(link)s: %(delay)d seconds since last good packet received." % {"link": comlink_name, "delay": delay}
                self._log( message )
                self.summary += message + "\n"
            s_type = "Q680-REMOTE"
        else:
                message = "No information available on packet delays."
                self._log( message )
                self.summary += message + "\n"

        # Count backed up packets
        reg_comlink_status = re.compile( "(\w+) Comlink Status.*?\r\n(?:[^ ][^\r\n]+?\r\n)*?[.]{3}queue size is (\d{1,5}) packets[.]\r\n(?:[^ ][^\r\n]+\r\n)*?((?:prio \d{1,5} packets[:] \d{1,5}.*?\r\n)+)", re.M )
        reg_prio_counts = re.compile( "prio \d{1,5} packets[:] (\d{1,5})" )

        matches = reg_comlink_status.findall( lines )

        if matches:
            count = len( matches )
            index = 0
            while index < count:
                match = matches[index]
                comlink_name = match[0]
                queue_size   = int( match[1] )
                prio_list    = match[2]
                packet_count = 0
                results = reg_prio_counts.findall( prio_list )
                if results:
                    for result in results:
                        packet_count += int( result )
                if packet_count < 50:
                    message = "%s is not backed up." % comlink_name
                    self._log( message )
                    self.summary += message  + "\n"
                elif packet_count <= queue_size:
                    message = "%(link)s backed up %(count)d/%(total)d packets." % {"link": comlink_name, "count": packet_count, "total": queue_size}
                    self._log( message )
                    self.summary += message  + "\n"
                else:
                    message = "Number of backed up packets [%(count)d] is greater than queue size [%(total)d]." % {"count": packet_count, "total": queue_size}
                    self._log( message )
                    self.summary += message  + "\n"
                index += 1
        else:
            message = "Could not locate packet queue status."
            self._log( message )
            self.summary += message + "\n"

        # Locate and tally network outages
        self.parser.parse( self.log_messages )
        summaries = self.parser.get_summaries()
        count = 0
        for (key, outage_list) in summaries.iteritems():
            if (outage_list) and len(outage_list):
                count += 1
                for (date, count, duration) in outage_list:
                    message = "%s outages [%s] %d disconnects totaling %.2f hours" % (key, date, count, float(duration / 3600.0))
                    self._log( message )
                    self.summary += message + "\n"
                    s_outages.append((date[5:],float(duration/3600.0)))
        if count <= 0:
            message = "No outages encountered."
            self._log( message )
            self.summary += message + "\n"

        outage_string = ""
        for d,o in s_outages:
            if o >= 1.0:
                if outage_string == "":
                    outage_string = " Network outages: "
                else:
                    outage_string += ", "
                outage_string += "%s - %.2f hours" % (d,o)
        if len(outage_string) > 0:
            outage_string += '.'

        s_summary = ''
        if s_type == 'Q680-LOCAL':
            s_summary =  "[%s]%s: Running %d days.%s\n\n" % (s_type, s_name, s_uptime, outage_string)
        elif s_type == 'Q680-REMOTE':
            s_summary = "[%s]%s: DP running %d days.%s\n\n" % (s_type, s_name, s_uptime, outage_string)
        self.summary = "%s%s" % (s_summary, self.summary)

# === Station680 Class (END)/*}}}*/

# === Station330 Class/*{{{*/
"""-
    Evaluate health of a Q330
-"""
class Station330(Station):
    def __init__(self, name, action, loop_queue, config_file):
        Station.__init__(self, name, action, loop_queue)

        self.output = ""        # results of the checks script
        self.log_messages = ""  # purpose TBD
        self.summary = ""
        self.config_file = config_file

        self.protocol = "qdp"

        self.current_id = -1

    def save_ping_info(self, message):
        self.tmp_buffer += message + "\n"

    def ready(self):
        if self.name == "":
            self.name = "anonymous"

    def check(self):
        fh = open(self.config_file, 'r')
        lines = map(lambda l: l.strip(), fh.readlines())
        fh.close()

        ids = {}
        for line in lines:
            if len(line) < 8:
                continue
            parts = line.split(".")
            if len(parts) < 3:
                continue
            if parts[0] != "Q330":
                continue
            try:
                id = int(parts[1])
            except:
                continue
            ids[id] = None

        try:
            from CnC import QComm, QPing
            comm = QComm.QComm()
            comm.set_max_tries(3)
            comm.set_timeout(30.0)
            comm.set_verbosity(0)
            action = QPing.QPing()
            action.action = "monitor"
            action._print = self.save_ping_info
            parts = self.name.split('_')
            if len(parts) > 1:
                name = parts[1]
            else:
                name = parts[0]

            q330_boot_times = []
            qping_results = {}
            for id in sorted(ids.keys()):
                self.tmp_buffer = ""
                comm.set_from_file(str(id), self.config_file)
                self._log("Performing QDP Ping on Q330 #%d..." % id)
                self._log("  IP Address : %s" % str(comm.q330.getIPAddress()))
                self._log("  Base Port  : %d" % comm.q330.getBasePort())
                self._log("  Serial No. : %016lX" % comm.q330.getSerialNumber())
                self._log("  Auth Code  : %016lX" % comm.q330.getAuthCode())
                self._log("  Timeout    : %0.1f" % comm.q330.getReceiveTimeout())
                comm.execute(action)
                match = re.compile("Boot Time: (\d+[/]\d+[/]\d+ \d+[:]\d+ UTC)", re.M).search(self.tmp_buffer)
                if not match:
                    self._log("Could not locate boot time for Q330 #%d" % id)
                    continue
                boot_time = match.groups()[0]
                boot_summary = " Q330 #%d boot time: %s" % (id, boot_time)
                q330_boot_times.append(boot_summary)
                qping_results[id] = self.tmp_buffer.strip()
                self._log("qping_results[%d]:" % id)
                self._log("%s" % qping_results[id])

            if len(q330_boot_times) > 0:
                self.output += "[Q330]%s:" % name
                self.output += ",".join(q330_boot_times) + ".\n\n"
                for id in sorted(qping_results.keys()):
                    self.output += "Q330 #%d\n" % id
                    self.output += qping_results[id] + "\n\n"

        except ImportError, e:
            self._log("Failed to import CnC modules required for Q330 status.")
        except Exception, e:
            self._log("Exception: %s" % str(e))

# === Station330 Class (END)/*}}}*/

# === StationSlate Class/*{{{*/
"""-
Evaluate health of a Q330 based station
    If we could not login due to receiving an unexpected
    public key from the Slate, throw an exception so
    the caller can log the issue.
-"""
class StationSlate(Station):
    def __init__(self, name, action, loop_queue, continuity_only=False, versions_only=False, commands=[], commands_only=False):
        Station.__init__(self, name, action, loop_queue)

        self.prompt_pass = ""
        self.protocol = "ssh"
        self.port = 22

        self.output = ""        # results of the checks script
        self.log_messages = ""  # purpose TBD
        self.summary = ""

        self.commands_only = commands_only
        self.continuity_only = continuity_only
        self.versions_only = versions_only

        self.commands = commands
        self.version_files = {}
        self.version_queue = None
        self.need_update = {}

        self.transfer_list = [
            ( # Path
                '/opt/util', 
                [ # Sources
                    'Quasar.tar.bz2',
                    'CnC.tar.bz2',
                    'baler.py',
                    'checks.py',
                    'dlc.py',
                    'falcon.py',
                    'upipe.py',
                ]
            ),
        ]

        self.install_list = [
            ('Quasar', 'Quasar.tar.bz2'),
            ('CnC',    'CnC.tar.bz2')
        ]
        self.install_path = '/opt/util'

        self.script_list = [
            'baler.py',
            'checks.py',
            'dlc.py',
            'falcon.py',
            'upipe.py',
        ]

    def process_commands(self, commands):
        for command in commands:
            self.process_command(command)

    def process_command(self, command):
        self.reader.sendline(command)
        try:
            if not self.reader.prompt( timeout=self.comm_timeout ):
                raise ExTimeout("timeout on command '%s'" % command)
        except Exception, e:
            self._log( "exception details: %s" % str(e) )
            raise ExIncomplete, "command failed"
        self._log(self.reader.before)

    def needs_update(self, file):
        if not os.path.exists(file):
            return False
        if not len(self.version_files.keys()):
            return True
        if not len(self.need_update.keys()):
            return False
        key = file
        if (len(file) > 8) and (file[-8:] == '.tar.bz2'):
            key = file[:-8] + '.md5'
        if not self.version_files.has_key(key):
            return False
        if hashsum.sum(file, 'MD5') != self.version_files[key][1]:
            self._log("Update file '%s' does not match MD5 in versions file!" % file)
            return False
        if self.need_update.has_key(key):
            return True
        return False

    def transfer(self):
        self._log("Need Update: " + ", ".join(sorted(self.need_update.keys())))
        for (dst, srcs) in self.transfer_list:
            source_files = filter(lambda i: self.needs_update(i), srcs)
            if not len(source_files):
                continue
            port_str = ""
            auth_str = ""
            if self.port:
                port_str = "-P %s" % str(self.port)
            if self.proxy is not None:
                auth_str = "-o'NoHostAuthenticationForLocalhost=yes'"
            command = "scp %s %s %s %s@%s:%s/." % (port_str, auth_str, " ".join(source_files), self.username, self.address, dst)
            #command = "scp -o ConnectTimeout=%d %s %s@%s:%s/." % (self.comm_timeout, ' '.join(source_files), self.username, self.address, dst)
            self._log("spawning pexpect with command: %s" % command)
            try:
                reader = pexpect.spawn(command)
            except Exception, e:
                self._log( "exception details: %s" % str(e) )
                raise ExLaunchFailed, "Failed to run scp"

            self._log("waiting for password prompt...")
            try:
                idx = reader.expect(['password:', 'Are you sure you want to continue connecting'], timeout=self.comm_timeout)
                self._log("accepting key")
                if idx == 1:
                    reader.sendline("yes")
                    reader.expect(['password:'], timeout=self.comm_timeout)
            except Exception, e:
                self._log( "exception details: %s" % str(e) )
                raise ExIncomplete, "Did not receive password prompt"

            self._log("sending password")
            reader.sendline(self.password)
            try:
                reader.expect( [pexpect.EOF], timeout=self.transfer_timeout )
            except Exception, e:
                self._log( "exception details: %s" % str(e) )
                raise ExInvalidCredentials, "Pasword incorrect"
            self._log(reader.before)

            reader.close()

    def update(self):
        self._log("cd %s" % self.install_path)
        self.reader.sendline("cd %s" % self.install_path)
        if not self.reader.prompt( timeout=self.comm_timeout ):
            raise ExTimeout("timeout on update first cd command")
        self._log(self.reader.before)

        for (id, file_name) in self.install_list:
            md5_response = ''
            if not os.path.exists(file_name):
                continue
            if not self.needs_update(file_name):
                continue
            self._log(str((id, file_name)))
            file = self.install_path + '/' + file_name

            self.reader.sendline("(which md5sum &> /dev/null && md5sum %s) || (which md5 &> /dev/null && md5 %s)" % (file_name, file_name))
            try:
                if not self.reader.prompt( timeout=self.comm_timeout ):
                    raise ExTimeout("timeout on md5 command")
            except Exception, e:
                self._log( "exception details: %s" % str(e) )
                raise ExIncomplete, "command failed"
            md5_response = self.reader.before

            md5_hash = ''
            if type(md5_response) == str:
                match = re.compile('[0-9a-f]{32}', re.M).search(md5_response)
                if match:
                    md5_hash = match.group(0)
                    self._log("md5 hash: %s" % md5_hash)
            else:
                self._log("Failed to get md5 hash for %s" % id)

            #self._log("tar xjf %s 2> /dev/null" % file_name)
            self.reader.sendline("tar xjf %s 2> /dev/null" % file_name)
            try:
                if not self.reader.prompt( timeout=self.comm_timeout ):
                    raise ExTimeout("timeout on extract command")
            except Exception, e:
                self._log( "exception details: %s" % str(e) )
                raise ExIncomplete, "command failed"
            self._log(self.reader.before)

            #self._log("cd %s/%s" % (self.install_path, id))
            self.reader.sendline("cd %s/%s" % (self.install_path, id))
            try:
                if not self.reader.prompt( timeout=self.comm_timeout ):
                    raise ExTimeout("timeout on cd command")
            except Exception, e:
                self._log( "exception details: %s" % str(e) )
                raise ExIncomplete, "command failed"
            self._log(self.reader.before)

            self.reader.sendline("./install_%s.py" % id)
            try:
                self.reader.expect(['(slate or [manual])?'], timeout=self.comm_timeout)
            except Exception, e:
                self._log( "exception details: %s" % str(e) )
                raise ExIncomplete, "command failed"
            self._log(self.reader.before)

            self.reader.sendline("slate")
            try:
                if not self.reader.prompt( timeout=self.comm_timeout ):
                    raise ExTimeout("timeout on install mode selection")
            except Exception, e:
                self._log( "exception details: %s" % str(e) )
                raise ExIncomplete, "command failed"
            self._log(self.reader.before)

            self.reader.sendline("cd %s" % self.install_path)
            try:
                if not self.reader.prompt( timeout=self.comm_timeout ):
                    raise ExTimeout("timeout on second cd command")
            except Exception, e:
                self._log( "exception details: %s" % str(e) )
                raise ExIncomplete, "command failed"
            self._log(self.reader.before)

            self.reader.sendline("rm -rf %s*" % id)
            try:
                if not self.reader.prompt( timeout=self.comm_timeout ):
                    raise ExTimeout("timeout on clean (rm) command")
            except Exception, e:
                self._log( "exception details: %s" % str(e) )
                raise ExIncomplete, "command failed"
            self._log(self.reader.before)

            self.reader.sendline("echo '%s' > /opt/util/%s.md5" % (md5_hash, id))
            try:
                if not self.reader.prompt( timeout=self.comm_timeout ):
                    raise ExTimeout("timeout on .md5 file update")
            except Exception, e:
                self._log( "exception details: %s" % str(e) )
                raise ExIncomplete, "command failed"
            self._log(self.reader.before)

        self.reader.sendline("if [ ! -d \"/opt/util/scripts\" ]; then mkdir /opt/util/scripts; fi")
        try:
            if not self.reader.prompt( timeout=self.comm_timeout ):
                raise ExTimeout("timeout on scripts directory check/creation")
        except Exception, e:
            self._log( "exception details: %s" % str(e) )
            raise ExIncomplete, "command failed"
        self._log(self.reader.before)

        self._log("Beginning installation of scripts...")
        for script in self.script_list:
            script_src = "/opt/util/%s" % script
            script_dst = "/opt/util/scripts/%s" % script
            self.reader.sendline("if [ -e \"%s\" ]; then mv %s %s; fi" % (script_src, script_src, script_dst))
            try:
                if not self.reader.prompt( timeout=self.comm_timeout ):
                    raise ExTimeout("timeout on script installation")
            except Exception, e:
                self._log( "exception details: %s" % str(e) )
                raise ExIncomplete, "command failed"
            self._log(self.reader.before)

    def check(self):
        if (not self.versions_only) and (not self.commands_only):
            self.check_diskloop_continuity()

        if (not self.continuity_only) and (not self.commands_only):
            self.check_software_versions()

        if (not self.continuity_only) and (not self.versions_only):
            self.process_commands(self.commands)

        if (not self.continuity_only) and (not self.versions_only) and (not self.commands_only):
            check_script = 'checks.py'
            script_path  = '/opt/util/scripts/checks.py'

            self._log( "checking hash of %s" % check_script )
            self.reader.sendline("md5sum %s" % script_path)
            if not self.reader.prompt( timeout=self.comm_timeout ):
                raise ExTimeout("timeout on performing checks script md5")
            self.output += self.reader.before + "\n"

            self._log( "running checks script" )
            self.reader.sendline(script_path)
            if not self.reader.prompt( timeout=self.comm_timeout ):
                raise ExTimeout("timeout while running checks script")

            self._log( "storing checks output" )
            self.reader.sendline('cat /opt/util/output')
            if not self.reader.prompt( timeout=self.comm_timeout ):
                raise ExTimeout("timeout while reading checks output")
            self.output += self.reader.before


    def set_version_queue(self, version_queue):
        if version_queue and (version_queue.__class__.__name__ == 'Queue'):
            self.version_queue = version_queue

    def set_version_files(self, version_files):
        if version_files and (type(version_files) == dict):
            self.version_files = version_files

    def check_software_versions_OLD(self):
        md5_files = []

        self.reader.sendline("cd /opt/util/scripts && ls -1 * | xargs -l1 md5sum")
        if not self.reader.prompt( timeout=self.comm_timeout ):
            raise ExTimeout("timeout while checking md5sums")
        md5_files += self.reader.before.strip('\n').split('\n')[1:]

        self.reader.sendline("cd /opt/util && for FILE in `ls -1 *.md5`; do SUM=`cat $FILE`; echo \"$SUM  $FILE\"; done")
        if not self.reader.prompt( timeout=self.comm_timeout ):
            raise ExTimeout("timeout while checking .md5 files")
        md5_files += map(lambda n: n[:-5], self.reader.before.strip('\n').split('\n')[1:])

        for file in md5_files:
            self._log(file)

    def check_software_versions(self):
        for (file, ref_md5) in self.version_files.values():
            tries = 2
            attempt = 0
            while attempt < tries:
                summary = ''
                if (len(file) > 4) and (file[-4:] == '.md5'):
                    self.reader.sendline("cat %s" % file)
                    try:
                        if not self.reader.prompt(timeout=self.comm_timeout):
                            raise ExTimeout("Timeout on md5sum check")
                    except Eception, e:
                        self._log("Exception details: %s" % str(e))
                        raise
                    md5_response = self.reader.before
                else:
                    self.reader.sendline("(which md5sum &> /dev/null && md5sum %s) || (which md5 &> /dev/null && md5 %s)" % (file, file))
                    try:
                        if not self.reader.prompt( timeout=self.comm_timeout ):
                            raise ExTimeout("timeout on md5 command")
                    except Exception, e:
                        self._log("exception details: %s" % str(e))
                        raise ExIncomplete, "command failed"
                    md5_response = self.reader.before

                md5_hash = ''
                if type(md5_response) == str:
                    match = re.compile('[0-9a-f]{32}', re.M).search(md5_response)
                else:
                    match = None

                if match:
                    md5_hash = match.group(0)
                    #self._log("MD5 hash: %s" % md5_hash)
                    attempt = tries
                else:
                    attempt += 1
                    self._log("Failed attempt #%d to acquire md5sum for %s" % (attempt, file))

            summary = "%s %s" % (md5_hash, file)
            log_category = 'default'
            if ref_md5 != md5_hash:
                self.version_queue.put("%s:%s" % (self.name, summary))
                log_category = 'warning'
                self.need_update[os.path.basename(file)] = True
            self._log(summary, category=log_category)


    def check_diskloop_continuity(self):
        diskloop_config = "/etc/q330/DLG1/diskloop.config"
        LINE_MAX = 128
        space_pad = lambda c: ((c > 0) and [" " + space_pad(c-1)] or [""])[0]

        # determine which channels to check based on which files
        # are listed in the checks
        self.reader.sendline("ls -1 /opt/data/%s" % self.name[3:])
        if not self.reader.prompt( timeout=self.comm_timeout ):
            raise ExTimeout("timeout preparing for diskloop continuity check")
        ls_result = self.reader.before
        reg_file = re.compile("(\d{2}_LHZ)[.]idx")
        diskloop_files = sorted(set(reg_file.findall(ls_result)))

        # this regular expression will parse out the components of a line
        # from the archive file
        reg_info = re.compile("^([^ ]{1,5}) (\d{2}/[^ ]{3}) Span ([^ ]+) to ([^ ]+) (\d+ records), start index (\d+)")
        
        # process all LHZ channels
        for diskloop_file in diskloop_files:
            archive_file = self.output_directory + "/" + diskloop_file + ".txt"
            gap_file = self.output_directory + "/" + diskloop_file + "_gaps.txt"

            file_size = 0
            # create the archive file if it does not exist
            if not os.path.exists(archive_file):
                try:
                    fh = open(archive_file, "w+b")
                    fh.close()
                except Exception, e:
                    raise Exception("Station::check_diskloop_continuity() could not create archive file %s: %s" % (archive_file, str(e)))
            # if the file already exists, find out its size
            else:
                try:
                    file_size = os.stat(archive_file).st_size
                except:
                    pass
            # require file size to be a multiple of 128 (our line block size)
            if file_size % LINE_MAX:
                raise Exception, "Station::check_diskloop_continuity() invalid size (%d) for archive file %s." % (file_size, archive_file)

            if not os.path.exists(gap_file):
                try:
                    fh = open(gap_file, "w+b")
                    fh.close()
                except Exception, e:
                    raise Exception("Station::check_diskloop_continuity() could not create gap file %s: %s" % (gap_file, str(e)))

            # make sure the files have the correct permissions
            Permissions("EEIEEIEII", 1).process([archive_file, gap_file])

            start_date = ""
            end_date = ""
            last_index = -1

            archive_info = None
            # if there are already records in the archive, we need to
            # run a check to prevent overlaps
            if file_size >= LINE_MAX:
                try:
                    fh = open(archive_file, "r+b")
                except Exception, e:
                    raise Exception, "Station::check_diskloop_continuity() failed to open archive file %s for reading: %s." % (archive_file, str(e))

                # seek to the last record in the file
                last_record = 0
                if file_size > LINE_MAX:
                    last_record = file_size - LINE_MAX
                fh.seek(last_record, 0)

                # evaluate the last line, we will use it to tell dlutil the
                # start date for its scan
                last_line = fh.read(LINE_MAX)
                archive_info = reg_info.findall(last_line)[0]
                if archive_info and len(archive_info):
                    try:
                        # use the start date of the last record from the archive
                        # as the start date parameter to dlutil
                        start_date = archive_info[2]
                        # end date is now plus two years just to be sure ('til 2036)
                        end_date = time.strftime("%Y,%j,%H:%M:%S.0000", (int(time.localtime()[0] + 2),) + time.localtime()[1:])
                        last_index = int(archive_info[5])
                        self._log("archive info: %s" % str(archive_info), 'debug')
                    except:
                        pass 

            # prepare the command for the diskloop continuity check
            self._log(str(diskloop_file), 'debug')
            command = "/opt/util/scripts/dlc.py %s %s %s" % (diskloop_config, self.name[3:], '/'.join(diskloop_file.split('_')))
            if len(start_date) and len(end_date):
                command += " %s %s" % (start_date, end_date)
            self._log("start date: %s" % start_date, 'debug')
            self._log("end date:   %s" % end_date, 'debug')

            # run the diskloop continuity check on the Slate
            self._log("checking diskloop continuity for channel %s" % '-'.join(diskloop_file.split('_')))
            command += " 2> /dev/null"
            self.reader.sendline(command)
            if not self.reader.prompt( timeout=self.comm_timeout ):
                raise ExTimeout("timeout while performing diskloop continuity check")
            dlc_results = self.reader.before.strip('\n\r').split('\n')
            if (type(dlc_results) != list) or (len(dlc_results) < 2):
                self._log(str(type(dlc_results)), 'debug')
                self._log(str(len(dlc_results)), 'debug')
                self._log("no new data found", 'debug')
                continue
            self._log("command: %s" % command, 'debug')
            self._log("64-bit encoded buffer [%s]" % dlc_results[1], 'debug')
            self._log("channel %s" % '/'.join(diskloop_file.split('_')), 'debug')
            # "decompress" the data
            info = dlc.expand(dlc_results[1])

            self._log("file_size = %d" % file_size, 'debug')
            overwrite_last = False
            # if there were already records in the archive, check for an index
            # match in the latest from the Slate
            if last_index >= 0:
                self._log("searching for index match for %d" % last_index, 'debug')
                i = -1
                found = False
                for line_info in info:
                    i += 1
                    self._log("comparing indices: ref=%d new=%d" % (last_index, int(line_info[8])), 'debug')
                    if last_index == int(line_info[8]):
                        # index match found
                        found = True
                        break
                # if we find an index match signal that the last record in the
                # archive should be overwritten
                if found:
                    self._log("replace last line", 'debug')
                    info = info[i:]
                    if file_size >= LINE_MAX:
                        overwrite_last = True
                # if no index matched, re-run the diskloop continuity check 
                # on the Slate 
                elif archive_info:
                    self._log("no index matched, re-running command continuity check for channel %s" % '-'.join(diskloop_file.split('_')))
                    command = "/opt/util/scripts/dlc.py %s %s %s" % (diskloop_config, self.name[3:], '/'.join(diskloop_file.split('_')))
                    # use the archive's last record's end time as
                    # the start-time argument to dlutil
                    start_date = inc_tmsec(archive_info[3])
                    command += " %s %s" % (start_date, end_date)
                    command += " 2> /dev/null"
                    self.reader.sendline(command)
                    if not self.reader.prompt( timeout=self.comm_timeout ):
                        raise ExTimeout("timeout on dlc command")
                    dlc_results = self.reader.before.strip('\n\r').split('\n')
                    self._log("dlc raw data: [%s]" % dlc_results, 'debug')
                    if (type(dlc_results) != list) or (len(dlc_results) < 2):
                        self._log("no new data found")
                        continue
                    self._log("command: %s" % command, 'debug')
                    self._log("64-bit encoded buffer [%s]" % dlc_results[1], 'debug')
                    self._log("channel %s" % '/'.join(diskloop_file.split('_')), 'debug')
                    info = dlc.expand(dlc_results[1])

            self._log("POST EXPANSION VALUES", 'debug')
            for line_info in info:
                self._log(str(info), 'debug')

            # prepare the content for archiving
            lines = ""
            for line_info in info:
                self._log("tuple [%s]: %s" % (len(line_info), str(line_info)), 'debug')
                name       = line_info[0]
                location   = "%02d" % line_info[1]
                channel    = line_info[2]
                time_start = time.strftime("%Y,%j,%H:%M:%S", time.gmtime(line_info[3])) + ".%04d" % line_info[4]
                time_end   = time.strftime("%Y,%j,%H:%M:%S", time.gmtime(line_info[5])) + ".%04d" % line_info[6]
                records    = str(line_info[7])
                index      = str(line_info[8])
                line = "%s %s/%s Span %s to %s %s records, start index %s" % (name, location, channel, time_start, time_end, records, index)
                # pad the lines to 128 bytes so we can seek through the file
                line += space_pad((LINE_MAX - 1) - len(line)) + "\n"
                lines += line

            # write the newest lines to the archive file
            self._log("lines: %s" % lines, 'debug')

            try:
                fh = open(archive_file, "r+b")
            except Exception, e:
                raise Exception, "Station::check_diskloop_continuity() failed to open archive file %s for writing: %s." % (archive_file, str(e))
            if overwrite_last:
                fh.seek(file_size - LINE_MAX, 0)
            else:
                fh.seek(file_size, 0)

            self._log("writing at position: %s" % str(fh.tell()), 'debug')
            fh.write(lines)
            fh.flush()
            fh.seek(0,0)
            span_lines = fh.readlines()
            fh.close()
            fh = None

            # Record gaps
            reg_gap = re.compile('(\w{1,5}) (\d{2})[/](\w{3}) Span (\d{4},\d{3},\d{2}:\d{2}:\d{2}.\d{4}) to (\d{4},\d{3},\d{2}:\d{2}:\d{2}.\d{4}) (\d+) records, start index (\d+)')
            lines = ''
            match_list = reg_gap.findall(''.join(span_lines))
            end_time = None
            for match in match_list:
                if match:
                    station, location, channel = tuple(match[0:3])
                    if (match[3] == match[4]) and (int(match[5]) == 1):
                        continue
                    last_time  = end_time
                    start_time = match[3]
                    end_time   = match[4]
                    if last_time and (time_cmp(last_time, start_time) != 0):
                        sec, tmsec = time_diff(start_time, last_time)
                        line = "%s %s/%s Gap %s to %s (%d.%04d seconds)" % (station, location, channel, last_time, start_time, sec, tmsec)
                        line += space_pad((LINE_MAX - 1) - len(line)) + "\n"
                        lines += line
                        #self._log(line.strip())
            try:
                fh = open(gap_file, "r+b")
                fh.truncate(0)
            except Exception, e:
                raise Exception, "Station::check_diskloop_continuity() failed to open archive file %s for writing: %s." % (gap_file, str(e))
            fh.write(lines)
            fh.flush()
            fh.close()

# === StationSlate Class (END)/*}}}*/

# === StationBaler Class/*{{{*/
"""Evaluate health of a Baler"""
class StationBaler(Station):
    def __init__(self, action):
        Station.__init__(self, action)

        self.wget = "/usr/bin/wget"
        self.connected = True

        self.baler_address = self.address
        self.baler_port    = ""

    def set_baler_address(self, address):
        self.baler_address = address

    def set_baler_port(self, port):
        self.baler_port = port

    def connect(self):
        return 1

    def disconnect(self):
        return 1

    def power_on_baler(self):
        action_str = self.wget + " --user=" + self.username + " --password=" + self.password + " --post-data pwr=Turn\ on\ Baler\ Power&postdone=yes" " http://" + self.address + ":" + self.port

        pexpect.run( action_str )

    def get_file_list(self):
        action_str = self.wget + " http://" + self.baler_address + ":" + self.baler_port + "/files.htm"

        pexpect.run( action_str )

# === StationBaler Class (END)/*}}}*/

# === Helper Functions/*{{{*/
def time_cmp(a, b):
    s,t = time_diff(a, b)
    if s:
        return s
    return t

def time_diff(a, b):
    utime_a = time.mktime(time.strptime(a[:-5], "%Y,%j,%H:%M:%S"))
    utime_b = time.mktime(time.strptime(b[:-5], "%Y,%j,%H:%M:%S"))
    utime_diff = utime_a - utime_b

    tmsec_a = int(a[-4:])
    tmsec_b = int(b[-4:])
    tmsec_diff = tmsec_a - tmsec_b

    if utime_diff > 0:
        if tmsec_diff < 0:
            utime_diff -= 1
            tmsec_diff += 1000
    elif utime_diff < 0:
        if tmsec_diff > 0:
            utime_diff += 1
            tmsec_diff -= 1000

    return (utime_diff, tmsec_diff)

def inc_tmsec(date_string):
    tmsec = int(date_string[-4:])    
    utime = time.mktime(time.strptime(date_string[:-5], "%Y,%j,%H:%M:%S"))
    if tmsec == 9999:
        tmsec = 0
        utime += 1
    else:
        tmsec += 1
    dtime = time.localtime(utime)
    if dtime[8]:
        #utime = utime - 3600
        dtime = time.localtime(utime)
    return "%s.%04d" % (time.strftime("%Y,%j,%H:%M:%S", dtime), tmsec)

# === Helper Functions (END)/*}}}*/

