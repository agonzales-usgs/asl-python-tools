#!/usr/bin/env python
"""-
Checks work without issues on stations that don't require any
access to the DA. Luckily this is the majority of our stations,
and includes all those with bad comm-links.

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

from jtk.Interval import Interval # time based poller
from jtk.Logger import Logger     # logging mechanism
from jtk.permissions import Permissions # UNIX permissions
from jtk.station import Station680 # for diagnosing Q680 systems
from jtk.station import Station330 # for diagnosing Q330 systems
from jtk.station import Proxy


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


class Manager:
    def __init__(self, action, stop_queue):
        self.action = action
        self.stop_queue = stop_queue

        self.stations = {} # dictionary of station info
        self.proxies  = {} # dictionary of proxy info
        self.groups   = {} # dictionary of group info
        self.groups['NONE'] = {
            'name'   : 'NONE',
            'type'   : 'Group',
            'threas' : '10',
        }

        self.output_directory = ""
        self.types        = None
        self.selection    = None
        self.exclusion    = None

        self.continuity_only = False
        self.versions_only = False

        self.station_file = ""
        self.station_file_encrypted = False

        self.version_logger = Logger(prefix='deviations_')
        self.version_queue  = Queue.Queue()
        self.version_thread = None
        self.version_files  = []

        self.loops = []
        self.queue = Queue.Queue()


# ===== Mutators =====
    def set_file(self, name, encrypted=False):
        self.station_file = name
        self.station_file_encrypted = encrypted

    def set_continuity_only(self, only=True):
        self.continuity_only = only

    def set_versions_only(self, only=True):
        self.versions_only = only

    def set_selection(self, list):
        self.selection = list

    def set_exclusion(self, list):
        self.exclusion = list

    def set_types(self, list):
        self.types = list


# ===== Entry Point =====
    def start(self):
        self.init_dir()
        self.parse_configuration()
        self.read_version_file()
        self.start_threads()

        station_groups = {}

        group_names = self.groups.keys()
        if self.group_selection is not None:
            group_names = self.group_selection

        for station in self.stations.keys():
            group = 'NONE'
            if self.stations[station].has_key('group'):
                group = self.stations['group']
            add_station = True
            if (self.group_selection != None) and (group not in group_names):
                add_station = False
            if add_station
                if not station_groups.has_key(group):
                    station_groups[group] = []
                station_groups[group].append(station)
        
        for group in group_names:
            max_threads = self.max_threads
            if self.groups[group].has_key('threads'):
                max_threads = int(self.groups[group]['threads'])
            loop = ThreadLoop(self, group, self.action, station_groups[group] max_threads, self.version_queue)
            loop.set_version_queue()
            loop.start()
            self.loops.append(loop)

        while len(self.loops):
            message,loop = self.queue.get()
            if message == 'DONE':
                self.loops.remove(loop)
            # else: self._log(message, loop.group)

        self.stop_queue.put('DONE')

# ===== Long Running Threads =====
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
                else:
                    self.version_logger.set_log_note("")
                    self.version_logger.log(parts[0])

# ===== Read in the contents of the version file =====
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

# ===== Parse the configuration file =====
    def parse_configuration(self):
        """
           Build a data structure of the stations listed in a file:
           stations = [station1, station2, ..., stationN]
           station  = [property1, property2, ..., propertyN]
           property = [name, value]
              name in [name, type, address, username, password, netserv, server, port, proxy]
        """
        Permissions("EEIEEIEII", 1).process([self.station_file])

        lines = ""
        if self.station_file_encrypted:
            aes = Crypt.Crypt(asl.aescrypt_bin)
            aes.log_to_screen(False)
            aes.log_to_file(False)
            aes.set_mode(Crypt.DECRYPT)
            # TODO: Add option to read password from a file
            aes.get_password()
            lines = aes.crypt_data(src_file=self.station_file)
        else:
            fh = open( self.station_file, "r" )
            if not fh:
                raise Exception, "%s::open() could not open file: %s" % (self.__class__.__name__, station_file)
            lines = "".join(fh.readlines())
            fh.close()

        reg_stations   = re.compile('<\s*((\s*\[[^\]]+\]\s*)+)\s*>')
        reg_properties = re.compile('\[([^:]+)[:]([^\]]+)\]')

        matches = reg_stations.findall(lines)
        for match in matches:
            station = reg_properties.findall(match[0])
            if station:
                info = {}
                # Populate this pseudo-station's info
                for pair in station:
                    info[pair[0]] = pair[1]

                if not info.has_key('name'):
                    raise Exception("Found a station without a 'name' field")

                # Insert the pseudo-station into the correct category
                # - Station
                # - Group (Station Group)
                # - Proxy (SSH TCP Port Forwarding Tunnel)
                if info.has_key('type') and (info['type'] == 'Group'):
                    self.groups[info['name']] = info
                elif info.has_key('type') and (info['type'] == 'Proxy'):
                    self.proxies[info['name']] = info
                elif ((not self.selection) or (self.selection.count(info['name']))) and \
                     ((not self.types)     or (self.types.count(info['type'])))     and \
                     ((not self.exclusion) or (not self.exclusion.count(info['name']))):
                    if self.stations.has_key(info['name']):
                        raise Exception("Duplicate station name found '%(name)s'" % info)
                    self.stations[info['name']] = info
                    self.stations_fresh.append(info['name'])

# ===== create the archive directory if it does not exist =====
    def init_dir(self):
        self.output_directory = None
        self.version_directory = None


        if not self.output_directory:
            self.output_directory  = "%(HOME)s/stations" % os.environ
        if not os.path.exists(self.output_directory):
            try:
                os.makedirs(self.output_directory)
                Permissions("EEEEEEEIE", 1).process([self.output_directory])
            except:
                raise Exception, "CheckLoop::init_dir() could not create storage directory: %s" % self.output_directory

        self.output_directory += "/gsn"
        if not os.path.exists(self.output_directory):
            try:
                os.makedirs(self.output_directory)
                Permissions("EEEEEEEIE", 1).process([self.output_directory])
            except:
                raise Exception, "CheckLoop::init_dir() could not create storage directory: %s" % self.output_directory

        self.version_directory = self.output_directory + "/versions"
        if not os.path.exists(self.version_directory):
            try:
                os.makedirs(self.version_directory)
                Permissions("EEEEEEEIE", 1).process([self.version_directory])
            except:
                raise Exception, "CheckLoop::init_dir() could not create version directory: %s" % self.version_directory
        self.version_logger.set_log_path(self.version_directory)


class ThreadLoop:
    def __init__(self, manager, group, action, station_names, max_threads, version_queue):
        self.action = action
        self.manager = manager
        self.group = group

        self.max_threads  = max_threads
        self.thread_ttl   = 7200 # Should not take more than 2 hours
        self.threads      = []

        # Group based station tracking dictionaries
        self.stations_fresh    = station_names
        self.stations_retry    = [] # checks failed, try again
        self.stations_complete = [] # checks succeeded, done
        self.stations_expired  = [] # tried max number of times allowed
        self.stations_partial  = [] # stations that are missing information

        self.poll_interval = 0.10 # seconds
        self.poller = Interval(self.poll_interval, self.poll)

        self.poll_lock = thread.allocate_lock()
        self.done = False

    def is_done(self):
        return self.done

    # start the loop with the appropriate action
    def start(self):
        self.poller.start()

# ===== Preparation methods =====
    def prep_station(self, station, info):
        if info.has_key('type'):
            station.type = info['type']
        if info.has_key('name'):
            station.set_name(info['name'])
        if info.has_key('group'):
            station.set_group(info['group'])
        if info.has_key('address'):
            station.set_address(info['address'])
        if info.has_key('port'):
            station.set_port(info['port'])
        if info.has_key('username'):
            station.set_username(info['username'])
        if info.has_key('password'):
            station.set_password(info['password'])
        if info.has_key('prompt'):
            station.prompt_shell = info['prompt']
        if info.has_key('netserv'):
            list = info['netserv'].split(',')
            for item in list:
                station.add_netserv_log(item)
        if info.has_key('server'):
            list = info['server'].split(',')
            for item in list:
                station.add_server_log(item)
        station.info = info

    def prep_proxy(self, proxy, info, station=None):
        if info.has_key('type'):
            proxy.type = info['type']
        if info.has_key('name'):
            proxy.set_name(info['name'])
        if info.has_key('address'):
            proxy.set_address(info['address'])
        if info.has_key('port'):
            proxy.set_port(info['port'])
        if info.has_key('username'):
            proxy.set_username(info['username'])
        if info.has_key('password'):
            proxy.set_password(info['password'])
        if info.has_key('prompt'):
            proxy.prompt_shell = info['prompt']
        if info.has_key('local-address'):
            proxy.local_address = info['local-address']
        else:
            proxy.local_address = "127.0.0.1"
        if info.has_key('local-port'):
            proxy.local_port = info['local-port']
        if station is not None:
            proxy.station_address = station.address
            proxy.station_port = station.port
        proxy.info=info


  # Recursively determines a station's proxy chain
    def find_proxies(self, station, station_info):
        if station_info.has_key('proxy'):
            if self.proxies.has_key(station_info['proxy']):
                station.proxy = Proxy()
                station.proxy_info = self.proxies[station_info['proxy']]
                self.prep_proxy(station.proxy, station.proxy_info, station)
                # Look for any proxy upon which this proxy depends (nested proxy support)
                self.find_proxies(station.proxy, station.proxy_info)
            else:
                raise Exception("Could not locate proxy '%(proxy)s' associated with station '%(name)s'" % station_info)

  # Recursively starts a station's proxy chain
    def start_proxies(self, station, dir, depth=[1]):
        if station.proxy is not None:
            # The depth logic can be a little confusing. We need this in order
            # to track how many ~ characters are required in order to reach
            # the SSH shell from this level. By passing a list, we can modify
            # its contents before returning control to our parent, thereby
            # giving increment control to the child. This ensures that the
            # parent proxy has a higher depth value than its child proxy, and
            # on down the chain. The parents is dependent on the child proxy
            # to establish the next portion of the path before it can connect.
            # We connect the child proxy before calling this proxy's start
            # method to ensure that the threads all begin in the correct order.
            proxy = station.proxy
            proxy.log_file_name(dir + '/proxy.log')
            proxy.log_to_file()
            proxy.log_to_screen()
            proxy.set_output_directory(self.output_directory + '/' + staiton.name)
            self.start_proxies(proxy, dir, depth)
            proxy.depth = depth
            depth[0] = depth[0] + 1
            station._log("Starting proxy thread...")
            proxy.start()

    def summarize(self):
        # build a summary
        print "All checks completed."

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
                Permissions("EEEEEEEIE", 1).process([ydir])
            except:
                station._log("could not create directory %s" % ydir)
                return
        if not os.path.exists(dir):
            try:
                os.makedirs(dir)
                Permissions("EEEEEEEIE", 1).process([dir])
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
            Permissions("EEIEEIEII", 1).process([summary_file])
        except Exception, e:
            station._log("CheckLoop::record() failed to record data to file. Exception: %s" % str(e))


    def poll(self):
        if not self.poll_lock.acquire( 0 ):
            print "%s::poll() could not acquire lock" % self.__class__.__name__
            return

        try:
            # check for completed threads
            for station in self.threads:
                if not station:
                    self.threads.remove(station)
                elif station.is_done():
                    if station:
                        station._log( "Wrapping up thread (" + str(len(self.threads) - 1) + " threads remaining)" )
                        if self.action == 'check':
                            self.record(station)
                    self.threads.remove(station)
                    self.stations_complete.append(station.name)

            # check for failed threads
            while len(self.threads) < self.max_threads:
                # check for stations in original list
                if len(self.stations_fresh):
                    station_key = self.stations_fresh.pop(0)
                    station_info = self.manager.stations[station_key]
                # once the original list is exhausted, check for retry stations
                elif len(self.stations_retry):
                    station_key = self.stations_retry.pop(0)
                    station_info = self.manager.stations[station_key]
                # if there are no threads remaining all stations have been checked
                elif not len(self.threads):
                    self.summarize()
                    self.poller.stop()
                    self.done = True
                    #self.poll_lock.release()
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
                        raise ExStationTypeNotRecognized, "Station type '%(type)s' not recognized" % station_info
                    self.prep_station(station, station_info)
                    station._log("Finished prep_station()")
                    station._log("  address = %s" % str(station.address))
                    station._log("  port    = %s" % str(station.port))
                    self.find_proxies(station, station_info)

                    date = time.gmtime()

                    dir = self.output_directory + '/' + station.name
                    try:
                        if not os.path.exists(dir): os.makedirs(dir)
                        Permissions("EEEEEEEIE", 1).process([dir])
                    except:
                        raise Exception, "CheckLoop::init_dir() could not create directory: %s" % dir

                    dir += time.strftime("/%Y", date)
                    try:
                        if not os.path.exists(dir): os.makedirs(dir)
                        Permissions("EEEEEEEIE", 1).process([dir])
                    except:
                        raise Exception, "CheckLoop::init_dir() could not create directory: %s" % dir

                    dir += time.strftime("/%j", date)
                    try:
                        if not os.path.exists(dir): os.makedirs(dir)
                        Permissions("EEEEEEEIE", 1).process([dir])
                    except:
                        raise Exception, "CheckLoop::init_dir() could not create directory: %s" % dir

                    if self.action == 'check':
                        file = dir + '/checks.log'
                    elif self.action == 'update':
                        file = dir + '/update.log'

                    print "log file: ", file
                    station.log_file_name(file)
                    station.log_to_file()
                    station.log_to_screen()
                    station.set_output_directory(self.output_directory + '/' + station.name)

                    if not station.min_info():
                        self.stations_partial.append(station.name)

                    self.start_proxies(station, dir)
                    station._log("Starting station thread...")
                    station.start()
                    self.threads.append(station)
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

        self.poll_lock.release()
        self.manager.queue.put(('DONE', self))


# === Main Class /*{{{*/
class Main:
    def __init__(self):
        option_list = []
        option_list.append(optparse.make_option("-c", "--comm-application", dest="comm_app", action="store", help="path to application for connection to station"))
        option_list.append(optparse.make_option("-d", "--diskloop-continuity-only", dest="dco", action="store_true", help="check diskloop continuity, then exit"))
        option_list.append(optparse.make_option("-e", "--encrypted", dest="encrypted", action="store_true", help="station file contents are encrypted"))
        option_list.append(optparse.make_option("-g", "--groups", dest="groups", action="store", help="comma seperated list of groups to check/update"))
        option_list.append(optparse.make_option("-s", "--select", dest="selection", action="store", help="comma seperated list of stations names to check/update"))
        option_list.append(optparse.make_option("-T", "--thread-count", dest="max_threads", type="int", action="store", help="maximum number of simulatneous connection threads"))
        option_list.append(optparse.make_option("-t", "--type", dest="type", action="store", help="comma seperated list of station types to check/update"))
        option_list.append(optparse.make_option("-v", "--software-versions-only", dest="svo", action="store_true", help="check software versions, then exit"))
        option_list.append(optparse.make_option("-x", "--exclude", dest="exclusion", action="store", help="comma seperated list of stations names to exclude from checks/updates"))
        self.parser = optparse.OptionParser(option_list=option_list)
        self.parser.set_usage("""Usage: %s [options] <stations_file> <action>

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

        arg_location    = options.comm_app
        arg_continuity  = options.dco
        arg_encrypted   = options.encrypted
        arg_exclude     = options.exclusion
        arg_select      = options.selection
        arg_group_selection = options.groups
        arg_threads     = options.max_threads
        arg_type        = options.type
        arg_versions    = options.svo

        if len(args) != 2:
            self.usage()

        arg_file = args[0]
        arg_action = args[1]
        if arg_action not in ('check', 'update'):
            self.usage("Un-recognized action '%s'" % arg_action)

      # Perform Action
        max_threads = 10
        if arg_threads:
            max_threads = arg_threads
        stop_queue = Queue.Queue()
        manager = Manager(arg_action, stop_queue)
        manager.set_file(arg_file, arg_encrypted)
        if (arg_select):
            manager.set_selection(arg_select.split(','))
        if (arg_group_selection):
            manager.set_group_selection(arg_group_selection.split(','))
        if (arg_type):
            manager.set_types(arg_type.split(','))
        if arg_continuity and arg_versions:
            print "Cannot select options -d and -v simultaneously"
            self.parser.print_help()
            sys.exit(1)
        if arg_exclude:
            manager.set_exclusion(arg_exclude.split(','))
        if arg_action == 'check':
            manager.set_continuity_only(arg_continuity)
            manager.set_versions_only(arg_versions)
        manager.start()
        stop_queue.get()

# === Main Class (END) /*}}}*/

if __name__ == '__main__':
    Main().start()

