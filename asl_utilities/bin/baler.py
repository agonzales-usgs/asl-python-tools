#!/usr/bin/env python
import asl

import base64
import calendar
import gzip
import httplib
import optparse
import os
import re
import socket
import StringIO
import struct
import sys
import time
import urllib
import urllib2
import zlib

ZLIB_ZLIB =  0
ZLIB_GZIP = 16
ZLIB_AUTO = 32

class EBad(Exception): pass

class EBadDate(EBad): pass
class EBadHost(EBad): pass
class EBadPort(EBad): pass
class EBadMask(EBad): pass

def glob_match(expr, string):                                                                                                                                       
    if expr == '':
        if string == '': return True
        else: return False
    reg_str = '^'
    for c in expr:
        if   c == '*': reg_str += '.*'
        elif c == '+': reg_str += '.+'
        elif c == '?': reg_str += '.?'
        else:          reg_str += c
    reg_str += '$'
    if re.match(reg_str, string):
        return True
    return False


def parse_time(time_string):
    try:
        return calendar.timegm(time.strptime(time_string, '%Y,%j,%H:%M:%S'))
    except:
        try:
            return calendar.timegm(time.strptime(time_string, '%Y,%m,%d,%H:%M:%S'))
        except Exception, e:
            raise EBadDate()


class ZlibWrapper(object):
    def __init__(self):
        pass

    def compress(self, buffer):
        return zlib.compressobj.compress(buffer)

    def decompress(self, buffer):
        return zlib.decompressobj(ZLIB_AUTO+zlib.MAX_WBITS).decompress(buffer)


class GzipWrapper(object):
    def __init__(self):
        pass

    def compress(self, buffer):
        file = StringIO.StringIO()
        factory = gzip.GzipFile(fileobj=file)
        factory.write(buffer)
        return file.read()

    def decompress(self, buffer):
        file = StringIO.StringIO()
        factory = gzip.GzipFile(fileobj=file)
        file.write(buffer)
        return factory.read()


class Baler(object):
    def __init__(self, file):
        self._host       = "136.177.121.35"
        self._port       = 5381
        self._start_time = None
        self._end_time   = None
        self._wfdiscs    = []
        self._zlib       = ZlibWrapper()
        self._gzip       = GzipWrapper()
        self._max_tries  = 5
        self._verbosity  = 0
        self._file       = file

        self._station_mask  = None
        self._channel_mask  = None

        self._regex_wfdisc = re.compile('\/WDIR\/wfdisc\/[0-9A-Za-z]{2}-[0-9A-Za-z]{0,5}_[0-9]-[0-9]{14}[.]wfdisc[.]gz')
        octet_string = '(?:[2][5][0-5]|[2][0-4][0-9]|[1][0-9]\{2\}|[0-9]\{1,2\})'
        self._regex_ip = re.compile('^%s(?:[.]%s)\{3\}$' % (octet_string, octet_string))

    def set_start_time(self, time_string):
        try:
            self._start_time = float(parse_time(time_string))
        except EBadDate:
            raise EBadDate("Invalid start date '%s'" % time_string)

    def set_end_time(self, time_string):
        try:
            self._end_time = float(parse_time(time_string))
        except EBadDate:
            raise EBadDate("Invalid end date '%s'" % time_string)

    def set_max_tries(self, max_tries):
        self._max_tries = max_tries

    def set_station_mask(self, station_mask):
        regex_station = re.compile('^[0-9A-Za-z?*+]{1,5}$')
        if not regex_station.match(station_mask):
            raise EBadMask("Invalid value for station mask '%s'" % station_mask)
        self._station_mask = station_mask

    def set_channel_mask(self, channel_mask):
        regex_channel = re.compile('^[0-9A-Za-z?*+]{1,3}$')
        if not regex_channel.match(channel_mask):
            raise EBadMask("Invalid value for channel mask '%s'" % channel_mask)
        self._channel_mask = channel_mask

    def set_host(self, host_string):
        try:
            socket.gethostbyname(host_string)
        except socket.gaierror:
            raise EBadHost("Could not resolve address '%s'" % host_string)
        self._host = host_string

    def set_port(self, port):
        if type(port) != int:
            try:
                port = int(port)
            except:
                raise EBadPort("Invalid port value '%s'" % port)
        if (port < 0) or (port > 65535):
            raise EBadPort("Invalid port value '%d'" % port)
        self._port = port

    def set_verbosity(self, verbosity):
        self._verbosity = verbosity

    def format_bytes(self, bytes):
        count = 0
        first = True
        for byte in bytes:
            if (count % 8) == 0:
                print '',
            if (count % 16) == 0:
                count = 0
                if not first:
                    print
                else:
                    first = False
            print "%02x" % int(byte),
            count += 1
        print

    def build_url(self, path):
        return "http://%s:%d/%s" % (self._host, self._port, path.lstrip('/'))

    def get_list(self):
        retry = self._max_tries
        backoff = 0.2
        while retry:
            page = self.get(self.build_url('/WDIR/wfdisc'))
            if page:
                break
            time.sleep(backoff)
            backoff += backoff / 1.5
            retry -= 1
        if not page:
            print "Could not download page"
            return
        matches = sorted(self._regex_wfdisc.findall(page))
        for match in matches:
            #print match
            self._wfdiscs.append(match)

    def get_data(self):
        min_time_offset =  4 * 60 * 60  #  4 hours
        is_last = False
        wfdisc_name_regex = re.compile('_[0-9]-([0-9]{14})')

        for wfdisc in self._wfdiscs:
            if is_last:
                print "Reached end of estimated time window."
                break
            print "PROCESSING", wfdisc
            w_time = calendar.timegm(time.strptime(wfdisc_name_regex.search(wfdisc).groups()[0], '%Y%m%d%H%M%S'))
            if self._start_time > (w_time - min_time_offset):
                print "skipping wfdisc '%s' which is outside of the date range (%s - %s)" % (wfdisc, time.strftime("%Y/%m/%d (%j) %H:%M:%S", time.gmtime(self._start_time)), time.strftime("%Y/%m/%d (%j) %H:%M:%S", time.gmtime(self._end_time)))
                continue
            if self._end_time < (w_time - min_time_offset):
                is_last = True
            retry = self._max_tries
            backoff = 0.2
            while retry:
                print 'Download Attempt #%d: %s' % (self._max_tries - retry + 1, self.build_url(wfdisc))
                raw = self.get(self.build_url(wfdisc))
                if raw:
                    break
                time.sleep(backoff)
                retry -= 1
                backoff += backoff / 1.5
            if not raw:
                print 'Failed to download wfdisc'
                continue
            #print '[%d] %s' % (len(raw), self.build_url(wfdisc))
            #self.format_bytes(struct.unpack('>64B', raw[0:64]))

            retry = self._max_tries
            backoff = 0.2
            while retry:
                print 'Decompress Attempt #%d' % (self._max_tries - retry + 1,)
                page = self._zlib.decompress(raw)
                if len(page):
                    break
                time.sleep(backoff)
                retry -= 1
                backoff += backoff / 1.5
            if not len(page):
                print 'Failed to decompress wfdisc'
                continue

            print '[%d] %s' % (len(page), self.build_url(wfdisc))
            #print 'page:', page

            print '%d lines' % (len(page.split('\n')),)

            for line in page.split('\n'):
                if not len(line):
                    continue
                station,channel,start,_,_,date,end,_,rate,_,_,_,_,_,_,_,file,offset,_,timestamp = map(lambda i: i.strip(), line.split())
                start_u = time.strftime('%Y%m%d%H%M%S', time.gmtime(float(start)))
                end_u   = time.strftime('%Y%m%d%H%M%S', time.gmtime(float(end)))

                # Filter using the station, channel, start time, and end time masks
                if self._start_time and (float(end)   < self._start_time): continue
                if self._end_time   and (float(start) > self._end_time):   continue
                if self._station_mask  and not glob_match(self._station_mask, station):   continue
                if self._channel_mask  and not glob_match(self._channel_mask, channel):   continue

                timestamp_u = time.strftime('%Y%m%d%H%M%S', time.gmtime(float(timestamp)))
                print station, channel, start_u, date, end_u, timestamp_u, rate, offset, file
                url = self.build_url("WDIR/data/%s" % file)
                print "URL:", url, "@", str(offset)
                pre = time.time()
                record = self.get(url, 4096, offset, 3)
                post = time.time()
                if record:
                    print "Received", len(record), "bytes of data in %0.6f seconds" % (post - pre,)
                    self._fh.write(record)
                else:
                    print "GOT NOTHING"

    def run(self):
        print "      Source: %s:%s" % (self._host,str(self._port))
        print " Destination:", os.path.abspath(self._file)
        print "  Start Time:", self._start_time,
        if self._start_time: print "[%s]" % time.strftime("%Y/%m/%d (%j) %H:%M:%S", time.gmtime(self._start_time))
        else: print
        print "    End Time:", self._end_time,
        if self._end_time: print "[%s]" % time.strftime("%Y/%m/%d (%j) %H:%M:%S", time.gmtime(self._end_time))
        else: print
        print "Station Mask:", self._station_mask
        print "Channel Mask:", self._channel_mask

        self._fh = open(self._file, 'w+')
        self.get_list()
        self.get_data()

        #url = "http://%s:%d/%s" % (self._host, self._port, self._path)
        #print "URL:", url
        #data = self.get(url, count=512, start=0)
        #print "DATA[%d]: %s" % (len(data), base64.urlsafe_b64encode(data))

    def get(self, url, count=-1, start=0, tries=-1):
        if tries < 1:
            tries = self._max_tries
        record = None
        backoff = 0.25
        attempt = 1
        while attempt <= tries:
            if attempt > 1:
                time.sleep(backoff)
                backoff += backoff / 1.5
            try:
                handler = urllib2.HTTPHandler()
                request = urllib2.Request(url)
                if start < 0:
                    start = 0
                if count > 0:
                    request.add_header('Range', 'bytes=%s-%s' % (str(start),str(int(start)+int(count)-1)))
                    #print "Range: bytes=%d-%d" % (start,start+count-1)
                request.add_header('Cache-Control', 'no-cache')
                opener = urllib2.build_opener(handler)
                urllib2.install_opener(opener)
                page_handle = urllib2.urlopen(request)
                #print str(dir(page_handle))
                #record = ''.join(page_handle.readlines())
                record = page_handle.read()
            except KeyboardInterrupt:
                raise
            except Exception, e:
                print "Failed attempt #%d (GET %s)" % (attempt, url)
                print "  Caught Exception:", e.__class__.__name__, str(e)
            attempt += 1

        if record is None:
            print "Failed to retrieve record at index %s" % str(start)
        return record


class Main:
    def __init__(self):
        use_message = """usage: %prog [options] <outfile>"""

        option_list = []
        self._parser = optparse.OptionParser(add_help_option=False, usage=use_message)
        self._parser.add_option("-h", "--host", dest="host", action="store", help="hostname or IP address of baler")
        self._parser.add_option("-p", "--port", dest="port", action="store", help="port of baler web interface")
        self._parser.add_option("-s", "--station-mask", dest="station_mask", action="store", help="wildcard mask of station name(s)")
        self._parser.add_option("-c", "--channel-mask", dest="channel_mask", action="store", help="wildcard mask of channel name(s)")
        self._parser.add_option("--help", action="help", help="show this help message and exit")
        self._parser.add_option("-S", "--start-date", dest="start_date", action="store", help="date after and including this date: YYYY,(mm,|d)dd,HH:MM:SS")
        self._parser.add_option("-E", "--end-date", dest="end_date", action="store", help="data before and including this date: YYYY,(mm,|d)dd,HH:MM:SS")
        self._parser.add_option("-v", dest="verbosity", action="count", help="specify multiple times to increase verbosity")
        self._options, self._args = self._parser.parse_args()

    def usage(self, message=''):
        if message:
            print "E:", str(message)
        self._parser.print_help()
        sys.exit(1)

    def start(self):
        if len(self._args) != 1:
            self.usage()

        outfile = self._args[0]
        if os.path.exists(outfile):
            print "%s: the path already exists" % outfile
            sys.exit(1)

        self._factory = Baler(outfile)
        if self._options.station_mask:
            self._factory.set_station_mask(self._options.station_mask)
        if self._options.channel_mask:
            self._factory.set_channel_mask(self._options.channel_mask)
        if self._options.start_date:
            self._factory.set_start_time(self._options.start_date)
        if self._options.end_date:
            self._factory.set_end_time(self._options.end_date)
        if self._options.host:
            self._factory.set_host(self._options.host)
        if self._options.port:
            self._factory.set_port(self._options.port)
        self._factory.set_verbosity(self._options.verbosity)
        self._factory.run()

if __name__ == "__main__":
    try:
        import psyco
        #psyco.full()
        psyco.profile()
        print "Psyco JIT enabled."
    except ImportError:
        pass

    try:
        Main().start()
    except EBad, e:
        print "E:", str(e)
    except KeyboardInterrupt:
        print "Keyboard Interrupt [^C]"

