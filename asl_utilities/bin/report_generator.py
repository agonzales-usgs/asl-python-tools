#!/usr/bin/env python
import asl

from jtk.Database import Database



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
        option_list.append(optparse.make_option("-v", dest="verbosity", action="count", help="specify multiple times to increase verbosity"))
        self.parser = optparse.OptionParser(option_list=option_list)
        self.parser.set_usage("""Usage: %prog [options] [path]""")

    def usage(self, message=''):
        if message != '':
            print "E:", message
        self.parser.print_help()
        sys.exit(1)

    def start(self):
        self.options, self.args = self.parser.parse_args()

    def q330_line(self, station, uptime, q330_times):
        line = "%s: Slate running %d days, " % (station, uptime)
        q330_lines = []
        for (id, startup) in q330_times:
            q330_lines.append("Q330 #%d boot time: %s" % (id, startup))
        line += ', '.join(q330_lines) + '.'
        return line

    def q680_remote_line(self, station, dp_uptime, da_uptime, outages):
        line = "%s: DP running %d days, DA running %d days. %s" % self.outage_string(outages)
        return line

    def q680_local_line(self, station, uptime, outages):
        line = "%s: Running %d days. %s" % self.outage_string(outages)
        return line

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

