#!/usr/bin/env python
import asl

from jtk.Dataless import Dataless
from jtk.Dataless import Blockette
from jtk.Calib import Calib
from jtk.Timer import Timer

import glob
import os
import Queue
import re
import sys

def usage():
    print """usage: %s [NETWORK_MASK_]<STATION_MASK> <[[LOCATION_MASK]-]CHANNEL_MASK> [PERIOD]""" % os.path.basename(sys.argv[0])
    sys.exit(1)

resp_dir = "/qcwork/RESPS"

args = sys.argv[1:]

if len(args) < 2:
    usage()
if len(args) > 3:
    usage()

#reg_st = re.compile("")
#reg_ch = re.compile("")

correct = True
period = 50.0

network = "*"
station = ""
location = "*"
channel = ""

if args[0].startswith('_') or args[0].endswith('_'):
    usage()
if args[1].endswith('-'):
    usage()

st_parts = args[0].split('_',1)
if len(st_parts) > 1:
    network,station = st_parts
else:
    station = st_parts[0]

ch_parts = args[1].split('-',1)
if args[1].startswith('-'):
    location = ""
    channel = ch_parts[1]
else:
    if len(ch_parts) > 1:
        location,channel = ch_parts
    else:
        channel = ch_parts[0]

if len(args) > 2:
    try:
        period = float(args[2])
    except ValueError, e:
        usage()

resp_mask = "%s/RESP.%s.%s.%s.%s" % (resp_dir,network,station,location,channel)

t_timer = Timer()
t_timer.start()

print "Mask =", resp_mask

files = sorted(glob.glob(resp_mask))
print "files:", files

results = {}
timer = Timer()
for file in files:
    key = os.path.basename(file)
    _,n,s,l,c = key.split('.')
    if n == "":
        n = "??"
    st = "%s_%s" % (n,s)
    if l == "":
        l = "??"
    ch = "%s-%s" % (l,c)
    print "processing '%s'" % file
    print "  reading ...",
    timer.start()
    fh = open(file, 'r')
    lines = fh.readlines()
    fh.close()
    print "done (%f seconds)" % timer.split()
    print "  parsing ...",
    dataless = Dataless(lines, quiet=True)
    dataless.process()
    print "done (%f seconds)" % timer.split()
    print "  calculating ...",
    calib = Calib(dataless, st, ch)
    calib.calculate_calib(period, correct)
    results[key] = calib
    print "done (%f seconds)" % timer.split()
    timer.stop()
    print "took %f seconds" % timer.span()
    print

for resp,calib in sorted(results.items()):
    cor_str = ""
    if correct:
        cor_str = " (corrected)"
    print "[%s]>  CALPER=%f  CALIB=%f%s" % (resp.ljust(19), calib.calper, calib.calib, cor_str)

t_timer.stop()

print "Processed %d channels in %f seconds" % (len(results), t_timer.span())

