#!/usr/bin/env python
"""-
Checks work without issues on stations that don't require any
access to the DA. Luckily this is the majority of our stations,
and includes all those with bad comlinks.

The next order of business is keep a information base where station
information is stored. This should be encrypted where possible. Aespipe
works on q330dev, but not on catbox, so another option may need to
be developed.

Stations need to be pulled out of this list one at a time and processed.
Results must be stored in a tree similar to tr1 buffer, but by week.

Eventually we may want to hand parse a lot of the results to flag the
most problematic stations.
-"""
import asl

import optparse     # argument parsing
import getpass      # to get user's password
import os           # for getting environmental variables
import Queue        # communication beteween threads
import re           # regular expression support
import stat         # file modes
import string       # string manipulation functions
import subprocess   # run shell commands
import sys          # arguments
import thread       # provides a lock
import threading    # provides thread support
import time
import traceback

from jtk import pexpect      # expect lib
from jtk import Crypt        # wrapper for aescrypt

from jtk.Interval import Interval   # time based poller
from jtk.station import Station680 # for diagnosing Q680 systems
from jtk.station import Station330 # for diagnosing Q330 systems
from jtk.station import Proxy
from jtk.station import SecureProxy
from jtk.Logger import Logger

# Station exceptions
from jtk.station import ExStationTypeNotRecognized
from jtk.station import ExStationNotSupported
from jtk.station import ExStationDisabled


class ExceptionLoop(Exception):
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

class ExLoopDone(ExceptionLoop):
    """raised when all checks are complete"""


class ThreadStation:
    def __init__(self, action):
        self.station = None
        self.thread  = None
        self.start_time = None
        self.action = action

        self.lock_thread = thread.allocate_lock()
        self.station_info = None

    def start(self):
        if not self.station:
            raise Exception, "ThreadStation::start() empty station object"
        if not self.lock_thread.acquire(0):
            return 0
        self.thread = threading.Thread(None, self.station.run, args=[self.action])
        self.thread.start()
        self.start_time = time.mktime( time.gmtime() )
        return 1

    def stop(self):
        #self.thread.terminate()
        self.lock_thread.release()

    def is_alive(self):
        return self.thread.isAlive()

    def set_info(self, station_info):
        self.station_info = station_info
    def get_info(self, station_info):
        return self.station_info
        
    def set_station(self, station):
        self.station = station
    def get_station(self):
        return self.station


class StationLoop:
    def __init__(self, action, max_threads=10):
        self.proxies           = [] # list of proxies needed by some stations
        self.stations          = [] # initial list of stations
        self.stations_retry    = [] # checks failed, try again
        self.stations_complete = [] # checks succeeded, done
        self.stations_expired  = [] # tried max number of times allowed
        self.stations_partial  = [] # stations that are missing information
        self.action = action

        self.output_directory = ""

        self.thread_count = 0
        self.max_threads  = max_threads
        self.thread_ttl   = 7200 # Should not take more than 2 hours
        self.threads      = []

        self.types        = None
        self.selection    = None
        self.exclusion    = None
        self.station_file = ""
        self.station_file_encrypted = False
        self.poll_interval = 0.10 # seconds
        self.poller = Interval(self.poll_interval, self.poll)

        self.lock_poll = thread.allocate_lock()
        self.done = False
        self.continuity_only = False
        self.versions_only = False

        self.version_logger = Logger(prefix='deviations_')
        self.version_queue  = Queue.Queue()
        self.version_files  = []

    def is_done(self):
        return self.done

    def set_selection(self, list):
        self.selection = list

    def set_exclusion(self, list):
        self.exclusion = list

    def set_continuity_only(self, only=True):
        self.continuity_only = only

    def set_versions_only(self, only=True):
        self.versions_only = only

    def set_types(self, list):
        self.types = list

    def set_file(self, name, encrypted=False):
        self.station_file = name
        self.station_file_encrypted = encrypted

    def set_dir(self, directory):
        self.station_dir = directory

    # create the archive directory if it does not exist
    def init_dir(self):
        self.output_directory = None
        self.version_directory = None

        if not self.output_directory:
            self.output_directory  = "%(HOME)s/stations" % os.environ
        if not os.path.exists(self.output_directory):
            try:
                os.makedirs(self.output_directory)
                permissions = stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
                if os.stat(self.output_directory).st_mode != permissions:
                    os.chmod(self.output_directory, permissions)
            except:
                raise Exception, "CheckLoop::init_dir() could not create storage directory: %s" % self.output_directory

        self.output_directory += "/gsn"
        if not os.path.exists(self.output_directory):
            try:
                os.makedirs(self.output_directory)
                permissions = stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
                if os.stat(self.output_directory).st_mode != permissions:
                    os.chmod(self.output_directory, permissions)
            except:
                raise Exception, "CheckLoop::init_dir() could not create storage directory: %s" % self.output_directory

        self.version_directory = self.output_directory + "/versions"
        if not os.path.exists(self.version_directory):
            try:
                os.makedirs(self.version_directory)
                permissions = stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
                if os.stat(self.version_directory).st_mode != permissions:
                    os.chmod(self.version_directory, permissions)
            except:
                raise Exception, "CheckLoop::init_dir() could not create version directory: %s" % self.version_directory
        self.version_logger.set_log_path(self.version_directory)

# ===== Long Running Threads =====================================
    def start_threads(self):
        self.version_thread = threading.Thread(target=self._version_log_thread)
        self.version_thread.start()

    def stop_threads(self):
        self.version_queue.put('HALT')
        self.version_thread.join()

    def _version_log_thread(self):
        run = True
        while run:
            message = self.version_queue.get()
            if message == 'HALT':
                run = False
            else:
                parts = message.split(':', 1)
                if (len(parts) == 2) and (4 < len(parts[0]) < 9):
                    self.version_logger.set_log_note(parts[0])
                    self.version_logger.log(parts[1])

    def read_version_file(self):
        version_file = './software_versions'
        if os.path.exists(version_file) and os.path.isfile(version_file):
            fh = open(version_file, 'r')
            for line in fh.readlines():
                parts = line.split('#', 1)[0].split()
                if len(parts) > 1:
                    hash = parts[0]
                    file = parts[1]
                    self.version_files.append((file, hash))

    def start(self):
        if self.action == 'update':
            self.start_update()
        elif self.action == 'check':
            self.start_check()

    # initialize the update process
    def start_update(self):
        self.init_dir()
        self.parse_configuration()
        self.poller.start()

    # initialize the check process
    def start_check(self):
        self.init_dir()
        self.parse_configuration()
        self.read_version_file()
        self.start_threads()
        self.poller.start()

    def prep_station(self, station, info):
        if info.has_key('station'):
            station.set_name(info['station'])
        if info.has_key('address'):
            station.set_address(info['address'])
        if info.has_key('port'):
            station.set_port(info['port'])
        if info.has_key('username'):
            station.set_username(info['username'])
        if info.has_key('password'):
            station.set_password(info['password'])
        if info.has_key('netserv'):
            list = info['netserv'].split(',')
            for item in list:
                station.add_netserv_log(item)
        if info.has_key('server'):
            list = info['server'].split(',')
            for item in list:
                station.add_server_log(item)

    def record(self, station):
        if not station:
            return
        date = time.gmtime()
        # by default, check output is stored in path as follows:
        # $HOME/stations/gsn/<station>/<year>/<j_day>/<HHMMSS>.chk
        dir = self.output_directory + '/' + station.name + time.strftime("/%Y/%j", date)
        file = time.strftime("%H%M%S.chk", date)

        # create the directories if they do not exist
        ydir = dir.rsplit('/',1)[0]
        if not os.path.exists(ydir):
            try:
                os.makedirs(ydir)
                permissions = stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
                if os.stat(ydir).st_mode != permissions:
                    os.chmod(ydir, permissions)
            except:
                station._log("could not create directory %s" % ydir)
                return
        if not os.path.exists(dir):
            try:
                os.makedirs(dir)
                permissions = stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
                if os.stat(dir).st_mode != permissions:
                    os.chmod(dir, permissions)
            except:
                station._log("could not create directory %s" % dir)
                return

        # if the target directory path exists but is not a directory, complain
        elif not os.path.isdir(dir):
            station._log("%s exists, and is not a directory, please resolve." % dir)
            return

        # write results into the summary file
        try:
            summary_file = dir + '/' + file
            fd = open(summary_file, "a")
            fd.write( station.summary )
            fd.write( station.output )
            fd.write( station.log_messages )
            fd.close()
            permissions = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH
            if os.stat(summary_file).st_mode != permissions:
                os.chmod(summary_file, permissions)
        except Exception, e:
            station._log("CheckLoop::record() failed to record data to file. Exception: %s" % str(e))


    def poll(self):
        if not self.lock_poll.acquire( 0 ):
            print "%s::poll() could not acquire lock" % self.__class__.__name__
            return

        try:
            # check for completed threads
            for thread in self.threads:
                if not thread:
                    self.threads.remove( thread )
                elif not thread.is_alive():
                    station = thread.get_station()
                    if station:
                        station._log( "Wrapping up thread (" + str(len(self.threads) - 1) + " threads remaining)" )
                        if self.action == 'check':
                            self.record( station )
                    self.threads.remove( thread )

            # check for failed threads
            while len(self.threads) < self.max_threads:
                # check for stations in original list
                if len(self.stations):
                    station_info = self.stations.pop(0)
                # once the original list is exhausted, check for retry stations
                elif len(self.stations_retry):
                    station_info = self.stations_retry.pop(0)
                # if there are no threads remaining all stations have been checked
                elif not len(self.threads):
                    self.summarize()
                    self.poller.stop()
                    self.done = True
                    #self.lock_poll.release()
                    raise ExLoopDone, "No stations remaining."
                else:
                    # This occurs when we have no stations
                    # in either the default or retry queues, and
                    # we have at least one but less than 
                    # self.max_threads still running.
                    break

                station = None
                try:
                    if ( station_info.has_key('disabled') and (station_info['disabled'] == 'true') ):
                        raise ExStationDisabled, "Station is disabled"
                    if ( station_info['type'] == 'Q680' ):
                        if self.continuity_only:
                            raise Exception("Continuity checks, Q680s not supported")
                        if self.versions_only:
                            raise Exception("Software version checks, Q680s not supported")
                        if self.action == 'update':
                            raise Exception("Software update, Q680s not supported")
                        station = Station680(self.action)
                    elif ( station_info['type'] == 'Q330' ):
                        station = Station330(self.action, legacy=False, continuity_only=self.continuity_only, versions_only=self.versions_only)
                        if self.action == 'check':
                            station.set_version_queue(self.version_queue)
                            station.set_version_files(self.version_files)
                    elif ( station_info['type'] == 'Q330C' ):
                        station = Station330(self.action, legacy=True, continuity_only=self.continuity_only, versions_only=self.versions_only)
                        if self.action == 'check':
                            station.set_version_queue(self.version_queue)
                            station.set_version_files(self.version_files)
                    else:
                        raise ExStationTypeNotRecognized, "Station type not recognized"
                    self.prep_station(station, station_info)
                    self.find_proxies(station, station_info)

                    permissions = stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
                    date = time.gmtime()

                    dir = self.output_directory + '/' + station.name
                    try:
                        if not os.path.exists(dir): os.makedirs(dir)
                        if os.stat(dir).st_mode != permissions: os.chmod(dir, permissions)
                    except:
                        raise Exception, "CheckLoop::init_dir() could not create directory: %s" % dir

                    dir += time.strftime("/%Y", date)
                    try:
                        if not os.path.exists(dir): os.makedirs(dir)
                        if os.stat(dir).st_mode != permissions: os.chmod(dir, permissions)
                    except:
                        raise Exception, "CheckLoop::init_dir() could not create directory: %s" % dir

                    dir += time.strftime("/%j", date)
                    try:
                        if not os.path.exists(dir): os.makedirs(dir)
                        if os.stat(dir).st_mode != permissions: os.chmod(dir, permissions)
                    except:
                        raise Exception, "CheckLoop::init_dir() could not create directory: %s" % dir

                    if self.action == 'check':
                        file = dir + '/checks.log'
                    elif self.action == 'update':
                        file = dir + '/update.log'

                    station.log_file_name(file)
                    station.log_to_file()
                    station.log_to_screen()
                    station.set_output_directory(self.output_directory + '/' + station.name)


                    if not station.min_info():
                        self.stations_partial.append(station_info)
                    thread = ThreadStation(self.action)
                    thread.set_station( station )
                    thread.set_info( station_info )
                    station._log( "Starting thread" )
                    thread.start()
                    self.threads.append(thread)
                except Exception, e:
                    if station:
                        print "%s::poll() failed to create thread. Exception: %s" % (self.__class__.__name__, str(e))
                    else:
                        print "%s::poll() failed to create station object. Exception: %s" % (self.__class__.__name__, str(e))
        except ExLoopDone, e:
            print "All stations have been processed"
        except Exception, e:
            print "%s::poll() caught exception: %s" % (self.__class__.__name__, str(e))
            (ex_f, ex_s, trace) = sys.exc_info()
            traceback.print_tb(trace)

        self.lock_poll.release()


    def find_proxies(self, station, station_info):
        if station_info.has_key('proxy'):
            for proxy_info in self.proxies:
                if proxy_info.has_key('station') and (proxy_info['station'] == station_info['proxy']):
                    if proxy_info['type'] == 'Proxy':
                        proxy = Proxy()
                    elif proxy_info['type'] == 'SecureProxy':
                        proxy = SecureProxy()
                    else:
                        raise ExProxyTypeNotRecognized, "Station type not recognized"
                    self.prep_station(proxy, proxy_info)
                    self.find_proxies(proxy, proxy_info)
                    station.add_proxy(proxy)

    def summarize(self):
        # build a summary
        print "All checks completed."

    def parse_configuration(self):
        """-
           Build a data structure of the stations listed in a file:
           stations = [station1, station2, ..., stationN]
           station  = [property1, property2, ..., propertyN]
           property = [name, value]
              name in [station, type, address, username, password, netserv, server]
        -"""
        permissions = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH
        if os.stat(self.station_file).st_mode != permissions:
            os.chmod(self.station_file, permissions)

        lines = ""
        if self.station_file_encrypted:
            aes = Crypt.Crypt(asl.aescrypt_bin)
            aes.log_to_screen(False)
            aes.log_to_file(False)
            aes.set_mode(Crypt.DECRYPT)
            aes.get_password()
            lines = aes.crypt_data(src_file=self.station_file)
        else:
            fh = open( self.station_file, "r" )
            if not fh:
                raise Exception, "%s::open() could not open file: %s" % (self.__class__.__name__, station_file)
            lines = "".join(fh.readlines())
            fh.close()

        reg_stations   = re.compile('<\s*((\s*\[[^>\]]+\]\s*)+)\s*>')
        reg_properties = re.compile('\[([\w]+)[:]([^\]]+)\]')

        matches = reg_stations.findall(lines)
        for match in matches:
            station = reg_properties.findall(match[0])
            if station:
                dict = {}
                for pair in station:
                    dict[pair[0]] = pair[1]
                if ((not self.selection) or (self.selection.count(dict['station']))) and ((not self.types) or (self.types.count(dict['type']))) and ((not self.exclusion) or (not self.exclusion.count(dict['station']))):
                    self.stations.append(dict)
                elif dict.has_key('type') and (dict['type'] in ['Proxy', 'SecureProxy']):
                    self.proxies.append(dict)


class Main:
    def __init__(self):
        option_list = []
        option_list.append(optparse.make_option("-a", "--address", dest="address", action="store", help="station IP address"))
        option_list.append(optparse.make_option("-c", "--comm-application", dest="comm_app", action="store", help="path to application for connection to station"))
        option_list.append(optparse.make_option("-d", "--diskloop-continuity-only", dest="dco", action="store_true", help="check diskloop continuity, then exit"))
        option_list.append(optparse.make_option("-e", "--encrypted", dest="encrypted", action="store_true", help="station file contents are encrypted"))
        option_list.append(optparse.make_option("-x", "--exclude", dest="exclusion", action="store", help="comma seperated list of stations names to exclude"))
        option_list.append(optparse.make_option("-f", "--file", dest="file", action="store", help="get station information from this file"))
        option_list.append(optparse.make_option("-n", "--name", dest="name", action="store", help="station name"))
        option_list.append(optparse.make_option("-P", "--port", dest="port", action="store", type="int", help="station connect port"))
        option_list.append(optparse.make_option("-p", "--password", dest="password", action="store", help="station login password"))
        option_list.append(optparse.make_option("-s", "--select", dest="selection", action="store", help="comma seperated list of stations names to check"))
        option_list.append(optparse.make_option("-T", "--thread-count", dest="thread_count", type="int", action="store", help="maximum number of simulatneous connection threads"))
        option_list.append(optparse.make_option("-t", "--type", dest="type", action="store", help="comma seperated list of station types to check"))
        option_list.append(optparse.make_option("-u", "--username", dest="username", action="store", help="station login username"))
        option_list.append(optparse.make_option("-v", "--software-versions-only", dest="svo", action="store_true", help="check software versions, then exit"))
        self.parser = optparse.OptionParser(option_list=option_list)
        self.parser.set_usage("""Usage: %s [options] <action>

    action: 
      update - update station software 
      check  - check station health""" % (sys.argv[0].split('/')[-1],))

    def usage(self, message=''):
        if message != '':
            print "E:", message
        self.parser.print_help()
        sys.exit(1)

    def start(self):
        options, args = self.parser.parse_args()

        arg_address     = options.address
        arg_location    = options.comm_app
        arg_continuity  = options.dco
        arg_encrypted   = options.encrypted
        arg_exclude     = options.exclusion
        arg_file        = options.file
        arg_name        = options.name
        arg_port        = options.port
        arg_password    = options.password
        arg_select      = options.selection
        arg_threads     = options.thread_count
        arg_type        = options.type
        arg_username    = options.username
        arg_versions    = options.svo

        if len(args) < 1:
            self.usage()
        if len(args) > 1:
            self.usage()
        arg_action = args[0]
        if arg_action not in ('check', 'update'):
            self.usage("Un-recognized action '%s'" % arg_action)

        if arg_file:
            thread_count = 10
            if arg_threads:
                thread_count = arg_threads
            loop = StationLoop(arg_action, thread_count)
            loop.set_file(arg_file, arg_encrypted)
            if (arg_select):
                loop.set_selection(arg_select.split(','))
            if (arg_type):
                loop.set_types(arg_type.split(','))
            if arg_continuity and arg_versions:
                print "Cannot select options -d and -v simultaneously"
                self.parser.print_help()
                sys.exit(1)
            if arg_exclude:
                loop.set_exclusion(arg_exclude.split(','))
            if arg_action == 'check':
                loop.set_continuity_only(arg_continuity)
                loop.set_versions_only(arg_versions)
            loop.start()
            while not loop.is_done():
                time.sleep(1)
            if arg_action == 'check':
                loop.stop_threads()

        else:
            """Run check on one station only"""
            # This should be updated to handle Q330s, or be deleted altogether
            if not arg_name:
                arg_name = raw_input( "Station Name: " )
            if not arg_address:
                arg_address = raw_input( "Host Address: " )
            if not arg_username:
                arg_username = raw_input( "Username: " )
            if not arg_password:
                arg_password = getpass.getpass( "Password: " )

            station = Station680(arg_action)
            station.set_name(arg_name)
            station.set_address(arg_address)
            station.set_username(arg_username)
            station.set_password(arg_password)
            if arg_location:
                station.set_com_app(arg_location)
            if arg_port:
                station.set_port(arg_port)
            try:
                station.connect()
                result = station.run(arg_action)
                station.disconnect()
                print station.output
                print station.log_messages
                print "Checks complete."
            except Exception, e:
                print "Caught exception: " + str(e)

if __name__ == '__main__':
    Main().start()

