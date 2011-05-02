#!/usr/bin/env python
import asl
import calendar
import optparse
import os
import sys
import time

from jtk.StationDatabase import StationDatabase

class Main:
    def __init__(self):
        option_list = []
        #option_list.append(optparse.make_option("-A", "--all-types", dest="all_types", action="store_true", help="change file objects of any type (includes devices)"))
        #option_list.append(optparse.make_option("-d", "--depth", dest="depth", action="store", type="int", help="recurse this many levels (includes current level)"))
        #option_list.append(optparse.make_option("-D", "--directories-only", dest="directories_only", action="store_true", help="only change permissions on directories"))
        #option_list.append(optparse.make_option("-F", "--files-only", dest="files_only", action="store_true", help="only change permissions on regular files"))
        #option_list.append(optparse.make_option("-g", "--group", dest="group", action="store", metavar="control_mask", help="control_mask for the group"))
        #option_list.append(optparse.make_option("-o", "--other", dest="other", action="store", metavar="control_mask", help="control_mask for all others"))
        #option_list.append(optparse.make_option("-s", "--smart", dest="smart", action="store_true", help="use smart options (mask 'PIP') for group"))
        #option_list.append(optparse.make_option("-S", "--smart-all", dest="smart_all", action="store_true", help="use smart options (mask 'PIP') for group and other"))
        #option_list.append(optparse.make_option("-u", "--user", dest="user", action="store", metavar="control_mask", help="control_mask for the owner"))
        option_list.append(optparse.make_option("-d", dest="database", action="store", help="database file to use for station and channel information"))
        option_list.append(optparse.make_option("-p", dest="path", action="store", help="station summary path"))
        option_list.append(optparse.make_option("-v", dest="verbosity", action="count", help="specify multiple times to increase verbosity"))
        self.parser = optparse.OptionParser(option_list=option_list)
        self.parser.set_usage("""Usage: %prog [options] [path]""")

        self.db = StationDatabase()
        self.db_file = "stations.db"
        self.summary_path = ""
        if os.environ.has_key('HOME'):
            self.summary_path = os.path.abspath(os.environ['HOME'] + "/stations/gsn")
        if not os.path.isdir(self.summary_path):
            self.summary_path = os.path.abspath(".")

    def usage(self, message=''):
        if message != '':
            print "E:", message
        self.parser.print_help()
        sys.exit(1)

    def start(self):
        self.options, self.args = self.parser.parse_args()
        if self.options.path:
            self.summary_path = os.path.abspath(self.options.path)
        if not os.path.isdir(self.summary_path):
            print "Could not locate summary directory '%s'" % self.summary_path
            sys.exit(1)

        if self.options.database:
            self.db_file = os.path.abspath(self.option.database)
        try:
            self.db.select_database(self.db_file)
        except:
            print "Could not open database '%s'" % self.db_file
            sys.exit(1)

        station_groups = []
        station_groups.append(('IMS',  self.db.get_stations_by_subset('CTBTO', False)))
        station_groups.append(('OTHER', self.db.get_stations_by_subset('CTBTO', True)))
        report_file = time.strftime("gsn-stations-%Y%j%m-%H%M%S.report")
        oh = open(report_file, 'w+')

        max_days = 4
        for subset,stations in station_groups:
            oh.write("%s INTERNET STATIONS (%s)\n.\n" % (subset, time.strftime("%Y/%m/%d")))
            for (_,network,station) in stations:
                now = time.gmtime()
                report_line = ""
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
                                report_line += self.q330_summary(file_path, network, station)
                            elif line_code == 'Q680-REMOTE':
                                report_line = line.split(']', 1)[1]
                                report_line += self.q330_summary(file_path, network, station)
                            else:
                                print "line_code '%s' did not match" % line_code
                    except OSError, e:
                        print "Exception> %s" % str(e)

                    if report_line != '':
                        break

                    now = time.gmtime(calendar.timegm(now) - 86400)

                if report_line == "":
                    report_line = "%s_%s: No summary found" % (network,station)
                print report_line
                oh.write(report_line + "\n.\n")

        oh.close()

    def q330_summary(self, file, network, station):
        problems = ""
        self.q330_channels(file, network, station)
        return problems

    def q680_remote_summary(self, file, network, station):
        problems = ""
        self.q680_channels(file, network, station)
        return problems

    def q680_local_summary(self, file, network, station):
        problems = ""
        self.q680_channels(file, network, station)
        return problems

    def q680_channels(self, file, network, station):
        #channels = self.db.get_channels(network=network, station=station)
        pass

    def q330_channels(self, file, network, station):
        #channels = self.db.get_channels(network=network, station=station)
        pass

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

