#!/usr/bin/env python
import asl

import os

def main():
    path = os.path.abspath(asl.path + "/utils/Azimuth.jar")
    proc = os.popen('java -jar "%s"' % path)

if __name__ == '__main__':
    main()

