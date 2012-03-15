#!/usr/bin/env python
import asl
import pprint

from jtk.Responses import Responses
from jtk.Responses import ResponsesThread
from jtk.Calib import Calib
import Queue

correct_calib = False
period = 1.0

queue = Queue.Queue()
channels = [
    ('IU', 'ANMO', '00', 'BHZ'),
    ('IU', 'ANMO', '00', 'BH1'),
    ('IU', 'ANMO', '00', 'BH2'),
    ('IU', 'ANMO', '10', 'BHZ'),
    ('IU', 'ANMO', '10', 'BH1'),
    ('IU', 'ANMO', '10', 'BH2'),
]

resp_list = []
for n,s,l,c in channels:
    resp_list.append(Responses(n,s,l,c,status_queue=queue))

print resp_list

thread = ResponsesThread(queue,resp_list)
thread.start()
status,(count,total,done) = ("preparing ...", (-1, -1, False))
while not done:
    progress = ""
    if count > -1:
        if (total > 0) and (count <= total):
            percent = float(count) / float(total) * 100.0
            progress = " - %d/%d (%0.1f%%)" % (count, total, percent)
        else:
            progress = " - %d" % count
    else:
        progress = " ..."

    print "%s%s" % (status, progress)

    status,(count,total,done) = queue.get()

# Print a pretty version of the parsed RESP file
#for resp in resp_list:
#    pprint.pprint(resp.resp_map)

print "All responses ready."

for resp in resp_list:
    calib = Calib(resp)
    calib.calculate_calib(period, False)
    print "[%s]>  CALPER=%f  CALIB=%f" % (resp.get_channel_key(), calib.calper, calib.calib)
    calib.calculate_calib(period, True)
    print "[%s]>  CALPER=%f  CALIB=%f  (Corrected)" % (resp.get_channel_key(), calib.calper, calib.calib)


