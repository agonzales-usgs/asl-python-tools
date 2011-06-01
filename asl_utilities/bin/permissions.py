#!/usr/bin/env python
import asl

from jtk.permissions import Main

if __name__ == '__main__':
    try:
        Main().start()
    except KeyboardInterrupt:
        print

