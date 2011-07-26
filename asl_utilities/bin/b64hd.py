#!/usr/bin/env python
import asl

import base64
import sys
from jtk import hexdump

while 1:
    try:
        data = raw_input()

        try:
            raw = base64.standard_b64decode(data.strip())
        except:
            print "Invalid Input."
            raise

        print hexdump.hexdump(raw)

    except KeyboardInterrupt:
        sys.exit(0)

