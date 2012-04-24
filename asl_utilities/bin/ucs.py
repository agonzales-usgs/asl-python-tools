#!/usr/bin/env python
import asl

import getpass
import os

from jtk import pexpect

paths = {
    "bin" : "%(HOME)s/dev/asl_package/asl_utilities/bin" % os.environ,
    "lib" : "%(HOME)s/dev/asl_package/asl_utilities/lib/python/jtk" % os.environ,
}


groups = [
    ("%(bin)s/stations.py" % paths,
     "%(bin)s/report_generator.py" % paths,
     "136.177.120.19:~/opt/asl_utilities/bin/."),
    ("%(lib)s/station.py" % paths,
     "%(lib)s/pxssh.py" % paths,
     "%(lib)s/pexpect.py" % paths,
     #"%(lib)s/Logger.py" % paths,
     "136.177.120.19:~/opt/asl_utilities/lib/python/jtk/."),
]

password = getpass.getpass("password: ")

for group in groups:
    command = "scp %s" % " ".join(group)
    reader = pexpect.spawn(command)
    reader.expect("password:")
    reader.sendline(password)
    reader.expect([pexpect.EOF])
    print reader.before
    reader.close()
