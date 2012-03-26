#!/usr/bin/env python
import asl
import pprint

from jtk.Dataless import Dataless
from jtk import Pretty
import Queue

def get_file_lines(file):
    return open(file, 'r').readlines()

file = "/qcwork/datalessSTUFF/littlesdataless" # EVERYTHING!
file = "/qcwork/datalessSTUFF/littlesANMO" # just ANMO

engine = Dataless(get_file_lines(file))

try:
    engine.process()
except Exception, e:
    print "Caught an Exception at:"
    print "  file '%s'" % file
    print "  %d lines skipped" % engine.skipped
    print "  on line %d of %d" % (engine.count, engine.total)
    print "    [%s]" % engine.line
    print
    print "Exception Details:"
    exc_type,exc_value,exc_traceback = sys.exc_info()                                               
    print traceback.format_exc()

#Pretty.pretty(engine.map)

for st_name,data in engine.map['stations'].items():
    channels = data['channels']
    for ch_name,ch_data in channels.items():
        if ch_name.endswith('BHZ'):
            epochs = sorted(ch_data['epochs'].items())
            #Pretty.pretty(epochs)

            if len(epochs) > 0:
                stamp,data = epochs[-1]
                b52 = data['info']
                start_date = b52.get_values(22)[0][0]
                end_date = b52.get_values(23)[0][0]
                depth = b52.get_values(13)[0][0]
                print "%s %s: %s (%s - %s)" % (st_name.ljust(8), ch_name.rjust(6), depth.rjust(12), start_date.ljust(23), end_date)




