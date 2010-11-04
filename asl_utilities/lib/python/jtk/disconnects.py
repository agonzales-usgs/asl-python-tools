#!/home/jdedwards/bin/python
import os
import re
import sys
import time
import string
import dircache
from log import Logger

class DisconnectParser:
    def __init__(self):
        self.logger = Logger()
        self.logger.set_log_file( "parse-test.log" )
        self.summaries = {}
        self.logger.set_log_to_screen(True)
        self.logger.set_log_to_file(True)

    def _log(self, str, category="info"):
        if category == "":
            self.logger.log( str )
        else:
            self.logger.log( str, category )

    def parse(self, lines):
        (connects, disconnects) = self.parse_messages( lines )
        key_list = connects.keys()
        for key in key_list:
            if disconnects.has_key(key):
                outages = self.parse_pairs( connects[key], disconnects[key] )
                results = self.parse_outages( outages )
                if len(results):
                    self.summaries[key] = results

    def parse_messages(self, lines):
        expr_date = "\d{4}\/\d{2}\/\d{2}\s*\r\n"
        expr_msgs = "\d{2}[:]\d{2}[:]\d{2}[ ][0-9A-Z_-]{1,}[.][0-9A-Z_-]{1,}[:][ ][^\r\n]*\r\n"
        regex_groups = re.compile( "(%s(?:%s)+)" % (expr_date, expr_msgs), re.M )
        groups = regex_groups.findall( lines )
        change_list = []
        connects = {}
        disconnects = {}
        if groups and len(groups):
            expr_date = "(\d{4}\/\d{2}\/\d{2})\s*?\r\n";
            regex_date = re.compile( "%s" % (expr_date,)  )
            for group in groups:
                date = string.strip( regex_date.search( group ).group(0) )
                group = re.sub( expr_date, "", group )
                group = re.sub( "(%s)" % (expr_msgs,), "%s \\1" % (date,), group )
                change_list.append( group )
            expr_date = "\d{4}\/\d{2}\/\d{2}";
            expr_msgs = "\d{2}[:]\d{2}[:]\d{2}[ ][0-9A-Z_-]{1,}[.][0-9A-Z_-]{1,}[:][ ][^\r\n]*\r\n";
            changes = ''.join(change_list)
            regex_filter = re.compile( "%s %s" % (expr_date, expr_msgs) )
            results = regex_filter.findall( changes )

            regex_disconnect = re.compile( "(?:Lost client connection)|(?:Disconnected due to write timeout)|(?:Client disconnect)" )
            regex_connect = re.compile( "(?:Client connection accepted)" )
            regex_servers = re.compile( "\d{4}\/\d{2}\/\d{2}[ ]\d{2}[:]\d{2}[:]\d{2}[ ][^.]+[.]([^:]+)[:]" )
            for result in results:
                if regex_connect.search(result):
                    key = regex_servers.findall(result)[0]
                    if not connects.has_key(key):
                        connects[key] = []
                    if result not in connects[key]: #remove duplicates
                        connects[key].append(result)
                if regex_disconnect.search(result):
                    key = regex_servers.findall(result)[0]
                    if not disconnects.has_key(key):
                        disconnects[key] = []
                    if result not in disconnects[key]: #remove duplicates
                        disconnects[key].append(result)
        else:
            message = "No outages encountered."
            self._log( message )

        # The following functions assume these are sorted by date, and won't work
        # otherwise
        for (key, values) in connects.iteritems():
            connects[key].sort()
            #print key, ":"
            #for value in values:
            #    print "  ", value
        for (key, values) in disconnects.iteritems():
            disconnects[key].sort()
            #print key, ":"
            #for value in values:
            #    print "  ", value

        return (connects, disconnects)

    def parse_pairs(self, connects, disconnects):
        outages = []
        more = 1
        connected = 1
        last_connect = 0
        last_disconnect = 0
        disconnect_time = 0

        regex_time = re.compile( '(\d{4}\/\d{2}\/\d{2}[ ]\d{2}[:]\d{2}[:]\d{2})' )
        if len(disconnects):
            while more:
                if connected and len(disconnects):
                    time_str = disconnects.pop(0)
                    time_str = string.strip(regex_time.search( time_str ).group(0))
                    last_disconnect = time.mktime(time.strptime(time_str, "%Y/%m/%d %H:%M:%S"))
                    if last_connect < last_disconnect:
                        connected = 0
                elif len(connects):
                    time_str = connects.pop(0);
                    time_str = string.strip(regex_time.search( time_str ).group(0))
                    last_connect = time.mktime(time.strptime(time_str, "%Y/%m/%d %H:%M:%S"))
                    connected = 1
                    if last_connect < last_disconnect:
                        connected = 0
                    else:
                        outages.append( (last_disconnect, last_connect) )
                else:
                    more = 0

        return outages

    def parse_outages(self, outages):
        outage_summary = {}
        summary = []

        if len(outages):
            while len(outages):
                (out_start, out_end) = outages.pop(0)
                span = 0
                archive_date = self.date_start(out_start)
                if self.same_day(out_start, out_end):
                    span = out_end - out_start
                else:
                    final_hour = self.date_end( out_start )
                    span = final_hour - out_start
                    out_start = self.date_start( final_hour + 60 )
                    outages.insert(0, (out_start, out_end) )
                date_string = self.date_str( archive_date )
                if outage_summary.has_key( date_string ):
                    (count, duration) = outage_summary[date_string]
                else:
                    count = 0
                    duration = 0
                count += 1
                duration += span
                outage_summary[date_string] = (count, duration)
            outage_order = sorted(outage_summary.keys())
            for date in outage_order:
                (count,duration) = outage_summary[date]
                summary.append((date, count, duration))
        return summary

    def get_summary(self, key):
        if self.summaries.has_key(key):
            return self.summaries[key]
        return None

    def get_summaries(self):
        return self.summaries

    def same_day(self, date_a, date_b):
        result = False
        tm_a = time.localtime( date_a )
        tm_b = time.localtime( date_b )
        if (tm_a.tm_year == tm_b.tm_year) and (tm_a.tm_yday == tm_b.tm_yday):
            result = True
        return result

    def date_str_us(self, date):
        return time.strftime( "%m/%d/%Y", time.localtime(date) )

    def date_str(self, date):
        return time.strftime( "%Y/%m/%d", time.localtime(date) )

    def time_str(self, date):
        return time.strftime( "%Y/%m/%d %H:%M:%S", time.localtime(date) )

    def date_start(self, date):
        time_str = time.strftime( "%Y/%m/%d 00:00:00", time.localtime(date) )
        return time.mktime( time.strptime( time_str, "%Y/%m/%d %H:%M:%S" ) )
        
    def date_end(self, date):
        time_str = time.strftime( "%Y/%m/%d 23:59:59", time.localtime(date) )
        return time.mktime( time.strptime( time_str, "%Y/%m/%d %H:%M:%S" ) )


# ===== Support for running this as a script =====================
def get_newest_chk( files ):
    regex_verify = re.compile( "^(\d{6})[.]chk$" )
    newest = "0"
    for file in files:
        match = regex_verify.search( file )
        if match:
            if int(newest[0:6]) < int(match.group(0)[0:6]): 
                newest = match.group(0)
    return newest

def usage( msg ):
    print "E:", msg
    print """
usage: disconnects.py <directory> [start-time [end-time]]
         time format: YYYY/MM/DD"""
    sys.exit(1)

if __name__ == "__main__":
    base_dir = ""
    start_time = time.mktime( time.strptime( time.strftime( "%Y/%m/%d 12:00:00", time.localtime() ), "%Y/%m/%d %H:%M:%S" ) )
    end_time = start_time

    regex_verify = re.compile( "^\d{4}\/\d{2}\/\d{2}$" )
    if (len(sys.argv) < 2) or (len(sys.argv) > 5):
        usage("Invalid number of arguments")
    if len(sys.argv) > 1:
        if not os.path.isdir(sys.argv[1]):
            usage("Invalid path [%s]" % sys.argv[1])
        base_dir = sys.argv[1]
    if len(sys.argv) > 2:
        if not regex_verify.search(sys.argv[2]):
            usage("Invalid start date")
        start_time = time.mktime( time.strptime( "%s 12:00:00" % sys.argv[2] , "%Y/%m/%d %H:%M:%S" ) )
    if len(sys.argv) > 3:
        if not regex_verify.search(sys.argv[3]):
            usage("Invalid end date")
        end_time = time.mktime( time.strptime( "%s 12:00:00" % sys.argv[3], "%Y/%m/%d %H:%M:%S" ) )

    done = False
    parser = DisconnectParser()
    date = start_time

    total_connects = []
    total_disconnects = []

    while date <= end_time:
        date += 86400
        tm_date = time.localtime( date )
        arg_dir  = "%s/%04d/%03d" % (base_dir, tm_date[0], tm_date[7])
        if os.path.isdir( arg_dir ):
            arg_file = get_newest_chk( dircache.listdir(arg_dir) )
            try:
                fh = open( arg_dir + "/" + arg_file, "r" )
                if not fh:
                    usage("Could not open check archive file")
                    sys.exit(1)
                lines = "".join(fh.readlines())
                fh.close()
                (connects, disconnects) = parser.parse_messages( lines )
                if connects:
                    total_connects.extend( connects )
                if disconnects:
                    total_disconnects.extend( disconnects )
            except IOError, e:
                print "Caught exception: " + e.__str__()

    if total_connects and total_disconnects:
        total_connects = list(set(total_connects))
        total_connects.sort()
        total_disconnects = list(set(total_disconnects))
        total_disconnects.sort()

        outages = parser.parse_pairs( total_connects, total_disconnects )
        parser.parse_outages( outages )
        results = parser.get_summary()

        print "Date, Disconnect Count, Duration"
        for (date, count, duration) in results:
            print "%s, %d, %.2f" % (date, count, float(duration / 60.0))

