#!/usr/bin/env python
import asl

import base64
from jtk import hexdump

while 1:
    try:
        data = raw_input()
        print

        try:
            raw = base64.standard_b64decode(data.strip())
        except:
            print "Invalid Input."
            raise

        print hexdump.hexdump(raw)

    except KeyboardInterrupt:
        print
        break

    print

