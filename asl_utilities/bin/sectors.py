#!/usr/bin/env python
import locale
import os
import sys

report_interval = 10 * 1024 * 1024
sector_size = 4096
try:
    locale.setlocale(locale.LC_ALL, 'en_US')
except:
    pass

def f_int(value):
    return locale.format("%d", value, grouping=True)

def f_float(value):
    return locale.format("%f", value, grouping=True)

class Logger:
    def __init__(self, log_file=None, truncate=False):
        self.handle = None
        self.file = None
        self.set_file(log_file, truncate)

    def set_file(self, log_file=None, truncate=False):
        if self.handle:
            self.handle.close()
            del self.handle
        self.file = log_file
        if log_file:
            mode = 'a'
            if truncate or (not os.path.exists(log_file)):
                mode = 'w+'
            self.handle = open(log_file, mode)
        else:
            self.handle = None

    def log(self, message):
        if self.handle:
            if message[-1] != '\n':
                message += '\n'
            self.handle.write(message)


if len(sys.argv) < 2:
    print "usage: %s <scan-file> [log-file]" % os.path.basename(sys.argv[0])
    sys.exit(1)

file = sys.argv[1]
if not os.path.exists(file):
    print "path '%s' does not exist" % file
    sys.exit(1)
if os.path.isdir(file):
    print "path '%s' is a directory" % file
    sys.exit(1)
if os.path.islink(file):
    print "path '%s' is a symbolic link" % file
    sys.exit(1)

logger = Logger()
log_file = None
if len(sys.argv) > 2:
    log_file = sys.argv[2]

if log_file:
    if os.path.exists(log_file):
        print "log file path '%' already exists"
        print "  please select an alternate path"
        sys.exit(1)
    logger.set_file(log_file, truncate=True)

print "%s START" % os.path.abspath(file)

bytes_read = 0
bytes_skipped = 0
sectors_accessed = 0
sectors_skipped = 0
last_report = 0

fh = open(file, "r")
data = "START"
while data:
    try:
        data = fh.read(sector_size)
        bytes_read += len(data)
        sectors_accessed += 1
    except IOError, e:
        message = "I/O Error at sector %s (byte %s)" % (f_int(fh.tell() / sector_size), f_int(fh.tell()))
        logger.log(message)
        print message
        fh.seek(sector_size, 1)
        print "Resuming at sector %s (byte %s)" % (f_int(fh.tell() / sector_size), f_int(fh.tell()))
        sectors_skipped += 1
        bytes_skipped += sector_size

    if (fh.tell() - last_report) >= report_interval:
        last_report = fh.tell()
        print "Sector %s (byte %s)" % (f_int(last_report / sector_size), f_int(last_report))

print
print "    read bytes : %s" % f_int(bytes_read)
print " skipped bytes : %s" % f_int(bytes_skipped)
print " -------------"
print "   total bytes : %s" % f_int(bytes_skipped + bytes_read)
print
print " accessed sectors : %s" % f_int(sectors_accessed)
print "  skipped sectors : %s" % f_int(sectors_skipped)
print " ----------------"
print "    total sectors : %s" % f_int(sectors_accessed + sectors_skipped)
print
print "%s COMPLETE" % os.path.abspath(file)

