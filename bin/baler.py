#!/usr/bin/env python
import asl

import base64
import gzip
import httplib
import optparse
import os
import re
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

class EBadDate(Exception): pass
class EBadHost(Exception): pass
class EBadPort(Exception): pass

def parse_time(time_string):
    try:
        return time.gmtime(time.strptime('%Y,%j,%H:%M:%S', time_string))
    except:
        try:
            return time.gmtime(time.strptime('%Y,%m,%d,%H:%M:%S', time_string))
        except:
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
    def __init__(self):
        self._host       = "136.177.121.35"
        self._port       = 5381
        self._start_time = ''
        self._end_time   = ''
        self._wfdiscs    = []
        self._zlib       = ZlibWrapper()
        self._gzip       = GzipWrapper()

        self._regex_wfdisc = re.compile('\/WDIR\/wfdisc\/[0-9A-Za-z]{2}-[0-9A-Za-z]{0,5}_[0-9]-[0-9]{14}[.]wfdisc[.]gz')
        octet_string = '(?:[2][5][0-5]|[2][0-4][0-9]|[1][0-9]\{2\}|[0-9]\{1,2\})'
        self._regex_ip = re.compile('^%s(?:[.]%s)\{3\}$' % (octet_string, octet_string))

    def set_start_time(self, time_string):
        self._start_time = parse_time(time_string)

    def set_end_time(self, time_string):
        self._end_time = parse_time(time_string)

    def set_host(self, host_string):
        if not self.regex_ip.match():
            raise EBadHost()
        self._host = host_string

    def set_port(self, port):
        if type(port) != int:
            try:
                port = int(port)
            except:
                raise EBadPort()
        if (port < 0) or (port > 65535):
            raise EBadPort()
        self._port = port

    def format_bytes(self, bytes):
        count = 0
        first = True
        for byte in bytes:
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
        retry = 5
        while retry:
            page = self.get(self.build_url('/WDIR/wfdisc'))
            if page:
                break
            time.sleep(1.0)
            retry -= 1
        if not page:
            print "Could not download page"
            return
        matches = sorted(self._regex_wfdisc.findall(page))
        for match in matches:
            #print match
            self._wfdiscs.append(match)

    def get_data(self):
        for wfdisc in self._wfdiscs:

            retry = 5
            while retry:
                print 'Download Attempt #%d: %s' % (6 - retry, self.build_url(wfdisc))
                raw = self.get(self.build_url(wfdisc))
                if raw:
                    break
                time.sleep(1.0)
                retry -= 1
            if not raw:
                print 'Failed to download wfdisc'
                continue
            #print '[%d] %s' % (len(raw), self.build_url(wfdisc))
            #self.format_bytes(struct.unpack('>64B', raw[0:64]))

            retry = 5
            while retry:
                print 'Decompress Attempt #%d' % (6 - retry,)
                page = self._zlib.decompress(raw)
                if len(page):
                    break
                time.sleep(1.0)
                retry -= 1
            if not len(page):
                print 'Failed to decompress wfdisc'
                continue

            #try:
            #page = self._gzip.decompress(raw)
            #except zlib.error:
            #    print 'Failed to decompress page'
            print '[%d] %s' % (len(page), self.build_url(wfdisc))
            #print 'page:', page

            print '%d lines' % (len(page.split('\n')),)

            for line in page.split('\n'):
                if not len(line):
                    continue
                station,channel,start,_,_,date,end,_,rate,_,_,_,_,_,_,_,file,offset,_,timestamp = line.split()
                start_u     = time.strftime('%Y%m%d%H%M%S', time.gmtime(float(start)))
                end_u       = time.strftime('%Y%m%d%H%M%S', time.gmtime(float(end)))
                #timestamp_u = time.strftime('%Y%m%d%H%M%S', time.gmtime(float(timestamp)))
                #print station, channel, start_u, date, end_u, timestamp_u, rate, offset, file

    def run(self):
        self.get_list()
        self.get_data()

        #url = "http://%s:%d/%s" % (self._host, self._port, self._path)
        #print "URL:", url
        #data = self.get(url, count=512, start=0)
        #print "DATA[%d]: %s" % (len(data), base64.urlsafe_b64encode(data))

    def get(self, url, count=-1, start=0):
        record = None
        try:
            handler = urllib2.HTTPHandler()
            request = urllib2.Request(url)
            if start < 0:
                start = 0
            if count > 0:
                request.add_header('Range', 'bytes=%d-%d' % (start,start+count-1))
                #print "Range: bytes=%d-%d" % (start,start+count-1)
            request.add_header('Cache-Control', 'no-cache')
            opener = urllib2.build_opener(handler)
            urllib2.install_opener(opener)
            page_handle = urllib2.urlopen(request)
            #print str(dir(page_handle))
            #record = ''.join(page_handle.readlines())
            record = page_handle.read()
        finally:
            return record


def main():
    try:
        option_list = []
        option_list.append(optparse.make_option("-v", dest="verbosity", action="count", help="specify multiple times to increase verbosity"))
        parser = optparse.OptionParser(option_list=option_list)
        options, args = parser.parse_args()

        factory = Baler()
        factory.run()
    except KeyboardInterrupt:
        print "Keyboard Interrupt [^C]"

if __name__ == '__main__':
    main()
