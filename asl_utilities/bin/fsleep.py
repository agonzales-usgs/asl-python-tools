#!/usr/bin/env python
import sys
import time

try:
    time.sleep(float(sys.argv[1]))
except KeyboardInterrupt:
    print
except:
    print "Usage: %s <sleep_duration>" % sys.argv[0]
    print "    sleep_duration - seconds to sleep (floating point allowed)"

