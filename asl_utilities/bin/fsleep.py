#!/usr/bin/env python
import os
import sys
import time

try:
    time.sleep(float(sys.argv[1]))
except KeyboardInterrupt:
    print
except:
    print "Usage: %s <sleep_duration>" % os.path.basename(sys.argv[0])
    print "    sleep_duration - seconds to sleep (floating point allowed)"

