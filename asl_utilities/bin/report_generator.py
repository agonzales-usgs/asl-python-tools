#!/usr/bin/env python
import asl
import calendar
import optparse
import os
import re
import sys
import time
import traceback

from jtk import StationDatabase

class Main:
    def __init__(self):
        option_list = []
        option_list.append(optparse.make_option(
            "-d",
            dest="database",
            action="store",
            help="Database file to use for station and channel information"))
        option_list.append(optparse.make_option(
            "-m",
            dest="max_days",
            action="store",
            type="int",
            help="Max number of days to search for check results"))
        option_list.append(optparse.make_option(
            "-n", "--networks",
            dest="networks",
            action="store",
            help="Comma seperated list of networks to process"))
        option_list.append(optparse.make_option(
            "-p",
            dest="path",
            action="store",
            help="Station summary path"))
        option_list.append(optparse.make_option(
            "-s", "--stations",
            dest="stations",
            action="store",
            help="Comma seperated list of stations to process"))
        option_list.append(optparse.make_option(
            "-v",
            dest="verbosity",
            action="count",
            help="Specify multiple times to increase verbosity"))
        self.parser = optparse.OptionParser(option_list=option_list)
        self.parser.set_usage("""Usage: %prog [options]""")

        self.db = StationDatabase.StationDatabase()
        self.db_file = "stations.db"
        self.summary_path = ""
        if os.environ.has_key('HOME'):
            self.summary_path = os.path.abspath(os.environ['HOME'] + "/stations")
        if not os.path.isdir(self.summary_path):
            self.summary_path = os.path.abspath(".")

    def usage(self, message=''):
        if message != '':
            print "E:", message
        self.parser.print_help()
        sys.exit(1)

    def start(self):
        self.options, self.args = self.parser.parse_args()
        if self.options.path: self.summary_path = os.path.abspath(self.options.path)
        if not os.path.isdir(self.summary_path):
            print "Could not locate summary directory '%s'" % self.summary_path
            sys.exit(1)

        if self.options.database:
            self.db_file = os.path.abspath(self.options.database)
        try:
            self.db.select_database(self.db_file)
        except:
            print "Could not open database '%s'" % self.db_file
            sys.exit(1)

        max_days = 4
        if self.options.max_days:
            max_days = self.options.max_days

        arg_networks = None
        if self.options.networks:
            arg_networks = map(lambda n: n.upper(), self.options.stations.split(','))

        arg_stations = None
        if self.options.stations:
            arg_stations = map(lambda s: s.upper(), self.options.stations.split(','))

        report_stations = map(lambda s: s[0].upper(), self.db.get_stations_by_subset('REPORT', False))

        station_groups = []
        station_groups.append(('IMS',  self.db.get_stations_by_subset('CTBTO', False)))
        station_groups.append(('OTHER', self.db.get_stations_by_subset('CTBTO', True)))
        report_file = time.strftime("stations-%Y%m%d-%H%M%S.report")
        oh = open(report_file, 'w+')

        for subset,stations in station_groups:
            oh.write("%s INTERNET STATIONS (%s)\n.\n" % (subset, time.strftime("%Y/%m/%d")))
            for (_,network,station) in stations:
                if arg_stations and (station.upper() not in arg_stations):
                    continue
                if arg_networks and (network.upper() not in arg_networks):
                    continue
                netst = network + station
                if report_stations and (netst.upper() not in report_stations):
                    continue

                now = time.gmtime()
                report_line = ""
                line_code = ""
                for i in range(0, max_days):
                    now_str = time.strftime("%Y,%j,%m,%d,%H,%M,%S", now)
                    year,jday,month,mday,hour,minute,second = now_str.split(',')
                    dir = os.path.abspath("%s/%s_%s/%s/%s" % (self.summary_path,network,station,year,jday))

                    try:
                        print "files: ", os.listdir(dir)
                        for file in sorted(filter(lambda f: (len(f) == 10) and (f[-4:] == '.chk'), os.listdir(dir)), reverse=True):
                            file_path = dir + "/" + file
                            print now_str
                            print dir
                            print file_path
                            print "opening:", file_path
                            fh = open(file_path, 'r')
                            line = ""
                            for line in fh:
                                if (len(line) > 1) and (line[0] == '['):
                                    break
                            fh.close()
                            line = line.strip()
                            line_code = line.split(']')[0].strip('[')
                            if line_code == 'Q330':
                                report_line = line.split(']', 1)[1]
                                report_line += self.q330_summary(file_path, network, station)
                            elif line_code == 'Q680-LOCAL':
                                report_line = line.split(']', 1)[1]
                                report_line += self.q680_local_summary(file_path, network, station)
                            elif line_code == 'Q680-REMOTE':
                                report_line = line.split(']', 1)[1]
                                report_line += self.q680_remote_summary(file_path, network, station)
                            else:
                                print "line_code '%s' did not match" % line_code
                            if len(report_line):
                                break
                    except OSError, e:
                        print "Exception> %s" % str(e)

                    if report_line != '':
                        break

                    now = time.gmtime(calendar.timegm(now) - 86400)

                if report_line == "":
                    report_line = "%s: No summary found." % station
                print report_line
                oh.write(report_line + "\n.\n")

        oh.close()

    def q330_summary(self, file, network, station):
        problems = self.q330_channels(file, network, station)
        return problems

    def q680_local_summary(self, file, network, station):
        problems = self.q680_channels(file, network, station)
        return problems

    def q680_remote_summary(self, file, network, station):
        problems = self.q680_channels(file, network, station)
        return problems

    def q680_channels(self, file, network, station):
        result = ""
        try:
            channels = self.db.get_channels(network=network, station=station)
            fh = open(file, 'r')
            check_summary = fh.read()
            fh.close()
            reg_timestamp = re.compile("UTC Timestamp:\s+(\d+-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})")
            date_regex = "\d{4}[/]\d{2}[/]\d{2}\s+\d{2}[:]\d{2}[:]\d{2}"
            reg_channels = re.compile("\d+\s+(\w{3,5})[.](\d{0,2}[-]\w{1,3})\s+[.]?\d+\s+%s\s+[-]\s+(%s)" % (date_regex, date_regex), re.M | re.S)
            reg_loc  = re.compile("^(?:[012]0)?$")
            reg_chan = re.compile("^(?:H[HN][12ENZ])|(?:BC[0-9])$")

            timestamp_matches = reg_timestamp.search(check_summary)
            channel_matches = reg_channels.findall(check_summary)
            if not timestamp_matches:
                raise Exception("No timestamp matches found.")
            if not channel_matches:
                raise Exception("No channel matches found.")
            check_channels = {}
            for s,c,t in channel_matches:
                check_channels[c] = (s,c,t)
            utc_timestamp = timestamp_matches.groups()[0]

            for _,_,l,c,_ in channels:
                key = c
                if l and len(l):
                    key = l + "-" + c
                if not check_channels.has_key(key):
                    missing_channels.append("%s" % key)
                else:
                    if reg_loc.match(l) and reg_chan.match(c):
                        print "Skipping event channel %s-%s" % (l,c)
                        continue
                    s,c,t = check_channels[key]
                    time_utc = calendar.timegm(time.strptime(utc_timestamp, "%Y-%m-%d %H:%M:%S"))
                    time_channel = calendar.timegm(time.strptime(t, "%Y/%m/%d %H:%M:%S"))
                    delay = time_utc - time_channel
                    if delay > 7200:
                        delayed_channels.append("%s" % (key.replace("_","-"),))
                if len(delayed_channels):
                    result += " Delayed Channels: %s." % (", ".join(delayed_channels),)
                if len(missing_channels):
                    result += " Missing Channels: %s." % (", ".join(missing_channels),)
        except Exception, e:
            print "%s-%s channel check Exception:" % (network,station), str(e)
            #(ex_f, ex_s, trace) = sys.exc_info()
            #traceback.print_tb(trace)
        return result

    def q330_channels(self, file, network, station):
        result = ""
        try:
            delayed_channels = []
            missing_channels = []
            channels = self.db.get_channels(network=network, station=station)
            fh = open(file, 'r')
            check_summary = fh.read()
            fh.close()
            reg_timestamp = re.compile("Slate Timestamp:\s+(\d+-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})")
            reg_channels = re.compile("(?:.*?(\w{3})\s+(\d+)\s+(\d+[:]?\d+)\s+(\w+)[.]buf)", re.M | re.S)
            reg_loc  = re.compile("^(?:[012]0)?$")
            reg_chan = re.compile("^(?:H[HN][12ENZ])|(?:BC[0-9])$")

            timestamp_matches = reg_timestamp.search(check_summary)
            channel_matches = reg_channels.findall(check_summary)
            if not timestamp_matches:
                raise Exception("No timestamp match found.")
            if not channel_matches:
                raise Exception("No channel matches found.")
            check_channels = {}
            for m,d,t,c in channel_matches:
                check_channels[c] = (m,d,t)
            slate_timestamp = timestamp_matches.groups()[0]

            for _,_,l,c,_ in channels:
                key = c
                if l and len(l):
                    key = l + "_" + c
                if not check_channels.has_key(key):
                    missing_channels.append("%s" % key)
                else:
                    if reg_loc.match(l) and reg_chan.match(c):
                        print "Skipping event channel %s-%s" % (l,c)
                        continue
                    m,d,t = check_channels[key]
                    time_parts = t.split(':')
                    if len(time_parts) == 1:
                        delayed_channels.append("%s" % key)
                    else:
                        time_slate = calendar.timegm(time.strptime(slate_timestamp, "%Y-%m-%d %H:%M:%S"))
                        time_channel = calendar.timegm(time.strptime("%s-%s-%s %s" % (time.strftime("%Y"),m,d,t), "%Y-%b-%d %H:%M"))
                        delay = time_slate - time_channel
                        if delay > 7200:
                            delayed_channels.append("%s" % (key.replace("_","-"),))
            if len(delayed_channels):
                result += " Delayed Channels: %s." % (", ".join(delayed_channels),)
            if len(missing_channels):
                result += " Missing Channels: %s." % (", ".join(missing_channels),)
        except Exception, e:
            print "%s-%s channel check Exception:" % (network,station), str(e)
            #(ex_f, ex_s, trace) = sys.exc_info()
            #traceback.print_tb(trace)
        return result

    def outage_string(self, outages):
        result_str = ""
        if len(outages):
            result_str = "Network outages: "
            strings = []
            for date,time in outages:
                strings.append("%s: %s hours" % (date,time))
            result_str += ', '.join(strings)
        return result_str

if __name__ == '__main__':
    try:
        Main().start()
    except KeyboardInterrupt:
        print

