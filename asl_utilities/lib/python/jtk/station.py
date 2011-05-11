"""
This module provides automated installation to the Kinemetrics Slate
at the new Q330 stations.
"""
"""
This module provides automated debugging and software upgrade 
tools for various stations
Station680 (Under Development): for debugging our Q680 stations
Station330 (Completed): for debugging and upgrading our Q330 stations

Expansion: Eventually I would like to modify this class to provide
           individual functions for each stage of the debug. The
           barriers I am seeing are due to limitations in pexpect,
           where 'before' is not available until after the next
           sendline() has been issued. Perhaps a modification of
           this module is feasible.

           Also, instead of pre-defined return types, I intened
           to introduce exceptions to describe the various errors
           one can run into.
"""

try:
    import datetime # to manage time differences
    import pexpect  # expect lib
    import pxssh    # ssh extension to pexepect
    import re       # regular expression parser
    import os       # file operations
    import stat     # file modes
    import sys      # arguments
    import time     # to get UTC current time
    import traceback

    from disconnects import DisconnectParser
    from Logger import Logger
    import dlc
except ImportError, e:
    raise ImportError (str(e) + """
A critical module was not found. 
Python 2.4 is the minimum recommended version.
You will need modules 'pexpect' and 'pxssh'.
""")


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

class Station:
    def __init__(self, action):
        # timeouts
        self.spawn_timeout    = 5
        self.comm_timeout     = 1800
        self.check_timeout    = self.comm_timeout
        self.parse_timeout    = self.comm_timeout
        self.search_timeout   = self.comm_timeout * 2
        self.transfer_timeout = self.comm_timeout * 2
        self.launch_timeout   = self.comm_timeout

        self.name     = None
        self.address  = None
        self.port     = None
        self.username = None
        self.password = None

        # must go through this proxy
        self.proxy     = None
        self.action   = action

        self.com_app   = None
        self.protocol  = None
        self.connected = None

        # expected prompts
        self.prompt_pass  = None
        self.prompt_user  = None
        self.prompt_shell = None

        self.verbosity = 3
        self.reader = None

        # new logging mechanism
        self.logger = Logger()
        self.logger.set_log_to_screen(True)
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

    def run(self, action):
        try:
            if action == 'check':
                self.run_check()
            elif action == 'update':
                self.run_update()
            elif action == 'proxy':
                self.run_proxy()
            else:
                self._log("Invalid action for station(s): '%s'" % action)
        except ExConnectFailed, e:
            self._log( str(e), "error" )
        except ExDisconnectFailed, e:
            self._log( str(e), "error" )
        except ExInvalidCredentials, e:
            self._log( str(e), "error" )
        except ExIncomplete, e:
            self._log( str(e), "error" )
        except ExLaunchFailed, e:
            self._log( str(e), "error" )
        except ExNoReader, e:
            self._log( str(e), "error" )
        except ExNotConnected, e:
            self._log( str(e), "error" )
        except ExStationNotSupported, e:
            self._log( str(e), "error" )
        except Exception, e:
            self._log( "Station::run() caught exception: %s" % str(e), "error" )
            (ex_f, ex_s, trace) = sys.exc_info()
            traceback.print_tb(trace)

    def run_check(self):
        self.ready()
        self.connect()
        self.check()
        self.disconnect()

    def run_update(self):
        self.ready()
        self.transfer()
        self.connect()
        self.update()
        self.disconnect()

    def run_proxy(self):
        self.ready()
        self.connect()
        self.disconnect()

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

    def add_proxy(self, proxy):
        if proxy:
            self.proxy = proxy

    def ready(self):
        if self.name == "":
            self.name = "anonamous"
        if self.address == "":
            raise ExIncomplete, "Server address not specified"
        if self.username == "":
            raise ExIncomplete, "Username not specified"
        if self.password == "":
            raise ExIncomplete, "Password not specified"

    def connect(self):
        self.ready()

        # If we have to go through a proxy, connect now
        # XXX: This isn't going to work, we are just creating two separate
        #      connections, neither going through the other.
        if self.proxy:
            self.proxy.connect()

        if self.protocol == "telnet":
            self.telnet_connect()
        elif self.protocol == "ssh":
            self.ssh_connect()
        else:
            raise ExProtocolUnknown, "The chosen protocol is not supported"
        self.connected = 1

    def disconnect(self):
        if not self.reader:
            raise ExNotConnected, "There was no connection established"

        if self.protocol == "telnet":
            self.telnet_disconnect()
        elif self.protocol == "ssh":
            self.ssh_disconnect()
        else:
            raise ExProtocolUnknown, "The chosen protocol is not supported"
        self.connected = 0

        # If we are using a proxy, close the connection now
        if self.proxy and self.proxy.connected:
            self.proxy.disconnect()

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
            server += " " + self.port
        self.reader.sendline( "open " + server )
        try:
            self._log( "opening connection to station" )
            match = self.reader.expect( [self.prompt_user], timeout=self.comm_timeout )
        except:
            raise ExConnectFailed, "Unable to open connection to " + self.address

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
            self._log( "closing telnet" )
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
            prompt = "\[" + self.username + "[@]" + self.name[3:] + "[:][~]\][$]"
            self._log( "opening ssh connection" )
            if ( self.port ):
                #self._log( "opening ssh connection to: " + self.username + "@" + self.address + ":" + self.port )
                self.reader.login( self.address, self.username, password=self.password, original_prompt=prompt, login_timeout=self.comm_timeout, port=self.port )
            else:
                #self._log( "opening ssh connection to: " + self.username + "@" + self.address )
                self.reader.login( self.address, self.username, password=self.password, original_prompt=prompt, login_timeout=self.comm_timeout )
        except Exception, e:
            self._log( "exception details: %s" % str(e) )
            raise ExConnectFailed, "Failed to ssh to station: %s" % str(e)

    def ssh_disconnect(self):
        try:
            self._log( "closing ssh connection" )
            self.reader.logout()
        except Exception, e:
            #self._log( "Station::ssh_disconnect() caught exception while trying to close ssh connection: %s" % e.__str__(), "error" )
            raise ExDisconnectFailed, "Disconnect Failed: %s" % str(e)

class SecureProxy(Station):
    def __init__(self):
        Station.__init__(self, 'proxy')

        self.prompt_pass = ""
        self.protocol = "ssh"

        self.output = ""        # results of the checks script
        self.log_messages = ""  # purpose TBD
        self.summary = ""

    def check(self):
        pass

class Proxy(Station):
    def __init__(self):
        Station.__init__(self, 'proxy')

        self.com_app     = os.popen('which telnet').read().strip()
        self.prompt_user = "User name\?:"
        self.prompt_pass = "Password:"
        self.protocol    = "telnet"

        self.output = ""        # results of the checks script
        self.log_messages = ""  # purpose TBD
        self.summary = ""

    def check(self):
        pass

class Station680(Station):
    def __init__(self, action):
        Station.__init__(self, action)

        self.netservs = []
        self.servers  = []

        # prompts to expect
        self.com_app     = os.popen('which telnet').read().strip()
        self.prompt_user = "User name\?:"
        self.prompt_pass = "Password:"
        self.protocol    = "telnet"

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
        self._log( "printing instrument list" )
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

"""-
Evaluate health of a Q330 based station
    If we could not login due to receiving an unexpected
    public key from the Slate, throw an exception so
    the caller can log the issue.
-"""
class Station330(Station):
    def __init__(self, action, legacy=False, continuity_only=False, versions_only=False):
        Station.__init__(self, action)

        self.prompt_pass = ""
        self.protocol = "ssh"

        self.output = ""        # results of the checks script
        self.log_messages = ""  # purpose TBD
        self.summary = ""

        self.legacy = legacy
        self.continuity_only = continuity_only
        self.versions_only = versions_only

        self.version_files = []
        self.version_queue = None

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

    def transfer(self):
        for (dst, srcs) in self.transfer_list:
            source_files = filter(lambda i: os.path.exists(i), srcs)
            if not len(source_files):
                continue
            port_str = ''
            if self.port:
                port_str = '-P %s' % str(self.port)
            command = "scp %s %s %s@%s:%s/." % (port_str, ' '.join(source_files), self.username, self.address, dst)
            #command = "scp -o ConnectTimeout=%d %s %s@%s:%s/." % (self.comm_timeout, ' '.join(source_files), self.username, self.address, dst)
            self._log("spawning pexpect with command: %s" % command)
            try:
                reader = pexpect.spawn(command)
            except Exception, e:
                self._log( "exception details: %s" % str(e) )
                raise ExLaunchFailed, "Failed to run scp"

            self._log("waiting for password prompt...")
            try:
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
        self.reader.prompt( timeout=self.comm_timeout )
        self._log(self.reader.before)

        for (id, file_name) in self.install_list:
            md5_response = ''
            if not os.path.exists(file_name):
                continue
            self._log(str((id, file_name)))
            file = self.install_path + '/' + file_name

            self.reader.sendline("(which md5sum &> /dev/null && md5sum %s) || (which md5 &> /dev/null && md5 %s)" % (file_name, file_name))
            try:
                self.reader.prompt( timeout=self.comm_timeout )
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
                self.reader.prompt( timeout=self.comm_timeout )
            except Exception, e:
                self._log( "exception details: %s" % str(e) )
                raise ExIncomplete, "command failed"
            self._log(self.reader.before)

            #self._log("cd %s/%s" % (self.install_path, id))
            self.reader.sendline("cd %s/%s" % (self.install_path, id))
            try:
                self.reader.prompt( timeout=self.comm_timeout )
            except Exception, e:
                self._log( "exception details: %s" % str(e) )
                raise ExIncomplete, "command failed"
            self._log(self.reader.before)

            #self._log("./install_%s.py" % id)
            self.reader.sendline("./install_%s.py" % id)
            try:
                self.reader.expect(['(slate or [manual])?'], timeout=self.comm_timeout)
            except Exception, e:
                self._log( "exception details: %s" % str(e) )
                raise ExIncomplete, "command failed"
            self._log(self.reader.before)

            self.reader.sendline("slate")
            try:
                self.reader.prompt( timeout=self.comm_timeout )
            except Exception, e:
                self._log( "exception details: %s" % str(e) )
                raise ExIncomplete, "command failed"
            self._log(self.reader.before)

            #self._log("cd %s" % self.install_path)
            self.reader.sendline("cd %s" % self.install_path)
            try:
                self.reader.prompt( timeout=self.comm_timeout )
            except Exception, e:
                self._log( "exception details: %s" % str(e) )
                raise ExIncomplete, "command failed"
            self._log(self.reader.before)

            #self._log("rm -rf %s*" % id)
            self.reader.sendline("rm -rf %s*" % id)
            try:
                self.reader.prompt( timeout=self.comm_timeout )
            except Exception, e:
                self._log( "exception details: %s" % str(e) )
                raise ExIncomplete, "command failed"
            self._log(self.reader.before)

            #self._log("echo '%s' > /opt/util/%s.md5" % (md5_hash, id))
            self.reader.sendline("echo '%s' > /opt/util/%s.md5" % (md5_hash, id))
            try:
                self.reader.prompt( timeout=self.comm_timeout )
            except Exception, e:
                self._log( "exception details: %s" % str(e) )
                raise ExIncomplete, "command failed"
            self._log(self.reader.before)

        self.reader.sendline("if [ ! -d \"/opt/util/scripts\" ]; then mkdir /opt/util/scripts; fi")
        try:
            self.reader.prompt( timeout=self.comm_timeout )
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
                self.reader.prompt( timeout=self.comm_timeout )
            except Exception, e:
                self._log( "exception details: %s" % str(e) )
                raise ExIncomplete, "command failed"
            self._log(self.reader.before)

    def check(self):
        if (not self.legacy) and (not self.versions_only):
            self.check_diskloop_continuity()

        if not self.continuity_only:
            self.check_software_versions()

        if (not self.continuity_only) and (not self.versions_only):
            check_script = 'checks.py'
            script_path  = '/opt/util/scripts/checks.py'
            #self._log( "checking for newer checks script (checks.py)" )
            #self.reader.sendline("if [ -e \"%s\" ]; then echo \"true\"; else echo \"false\"; fi" % script_path)
            #self.reader.prompt( timeout=self.comm_timeout )
            #reg_result = re.compile('((?:true)|(?:false))[^\n]*?$').search(self.reader.before)
            #result = "false"
            #if reg_result:
            #    result = reg_result.groups()[0]
            #self._log( "result of checks script is '%s'" % result )
            #if result != "true":
            #    self._log( "using default checks script (checks.pl)" )
            #    check_script = 'checks.pl'
            #    script_path  = '/opt/util/scripts/checks.pl'

            self._log( "checking hash of %s" % check_script )
            self.reader.sendline("md5sum %s" % script_path)
            self.reader.prompt( timeout=self.comm_timeout )
            self.output += self.reader.before + "\n"

            self._log( "running checks script" )
            self.reader.sendline(script_path)
            self.reader.prompt( timeout=self.comm_timeout )

            self._log( "storing checks output" )
            self.reader.sendline('cat /opt/util/output')
            self.reader.prompt( timeout=self.comm_timeout )
            self.output += self.reader.before


    def set_version_queue(self, version_queue):
        if version_queue and (version_queue.__class__.__name__ == 'Queue'):
            self.version_queue = version_queue

    def set_version_files(self, version_files):
        if version_files and (type(version_files) == list):
            self.version_files = version_files

    def check_software_versions_OLD(self):
        md5_files = []

        self.reader.sendline("cd /opt/util/scripts && ls -1 * | xargs -l1 md5sum")
        self.reader.prompt( timeout=self.comm_timeout )
        md5_files += self.reader.before.strip('\n').split('\n')[1:]

        self.reader.sendline("cd /opt/util && for FILE in `ls -1 *.md5`; do SUM=`cat $FILE`; echo \"$SUM  $FILE\"; done")
        self.reader.prompt( timeout=self.comm_timeout )
        md5_files += map(lambda n: n[:-5], self.reader.before.strip('\n').split('\n')[1:])

        for file in md5_files:
            self._log(file)

    def check_software_versions(self):
        #print self.version_files
        for (file, ref_md5) in self.version_files:
            summary = ''
            if (len(file) > 4) and (file[-4:] == '.md5'):
                self.reader.sendline("cat %s" % file)
                self.reader.prompt(timeout=self.comm_timeout)
                md5 = self.reader.before.strip('\n').split('\n')[1].strip()
            else:
                self.reader.sendline("md5sum %s" % file)
                self.reader.prompt(timeout=self.comm_timeout)
                md5 = self.reader.before.strip('\n').split('\n')[1].split(' ')[0].strip()
            summary = "%s %s" % (md5, file)
            log_category = 'default'
            if ref_md5 != md5:
                self.version_queue.put("%s:%s" % (self.name, summary))
                log_category = 'warning'
            self._log(summary, category=log_category)

    def check_diskloop_continuity(self):
        diskloop_config = "/etc/q330/DLG1/diskloop.config"
        if self.legacy:
            diskloop_config = "/etc/q330/diskloop.config"
        LINE_MAX = 128
        space_pad = lambda c: ((c > 0) and [" " + space_pad(c-1)] or [""])[0]

        # determine which channels to check based on which files
        # are listed in the checks
        self.reader.sendline("ls -1 /opt/data/%s" % self.name[3:])
        self.reader.prompt( timeout=self.comm_timeout )
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
            permissions = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH
            if os.stat(archive_file).st_mode != permissions:
                os.chmod(archive_file, permissions)
            if os.stat(gap_file).st_mode != permissions:
                os.chmod(gap_file, permissions)

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
            self.reader.prompt(timeout=self.comm_timeout)
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
                    self.reader.prompt(timeout=self.comm_timeout)
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

"""Evaluate health of a Baler"""
class StationBaler(Station):
    def __init__(self, action):
        Station.__init__(self, action)

        self.wget = "/usr/bin/wget"
        self.connected = 1

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

