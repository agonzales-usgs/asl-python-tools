#!/usr/bin/env python
import os
import re
import sys
import time

def find_process(arg_list):
    #print "searching for process with arguments:", arg_list
    pid = None
    proc = os.popen("ps x -o pid,args")
    lines = proc.readlines()
    #print lines
    for line in lines:
        tpid,rest = line.split(None, 1)
        args = rest.split()
        if len(args) != len(arg_list):
            continue

        found = True
        for a,b in zip(arg_list, args):
            if a != b:
                #print "  '%s' != '%s'" % (a, b)
                found = False
                break
            else:
                #print "  '%s' == '%s'" % (a, b)
                pass
        if not found:
            continue

        pid = tpid
        break

    return pid

pid_file = "/tmp/jdedwards.archd.pid"
executable = "/opt/data/bin/archd"
config_file = "/etc/q330/DLG1/diskloop.config"

arg_list = [executable, config_file]

pid = find_process(arg_list)
if pid is not None:
    print "Found [%s] `%s`" % (pid, ' '.join(arg_list))
else:
    os.spawnv(os.P_NOWAIT, arg_list[0], arg_list)

    check_interval = 0.25
    remaining_checks = 20
    while remaining_checks > 0:
        pid = find_process(arg_list)
        if pid is not None:
            remaining_checks = 0
        else:
            remaining_checks -= 1
            sys.stdout.write(".")
            sys.stdout.flush()
            time.sleep(check_interval)
    sys.stdout.write("\n")

    if pid is not None:
        print "Spawned [%s] `%s`" % (pid, ' '.join(arg_list))
    else:
        print "Process did not appear to spawn"

