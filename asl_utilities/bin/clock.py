#!/usr/bin/env python
import calendar
import os
import re
import shlex
import subprocess
import sys
import time

archive = "/tr1/telemetry_days"
days    = 10
max     = 100
now     = calendar.timegm(time.gmtime())

networks = ['CU', 'IC', 'IU']
stations = None
#stations = ['ANMO', 'KOWA', 'MSKU']

qualities = {}
for station in os.listdir(archive):
    if station[0:2] not in networks:
        continue
    if stations and (station[3:] not in stations):
        continue

    qualities[station] = {}
    station_qualities = qualities[station]
    count = 0
    for idx in range(0, max):
        if count > days:
            break
        timestamp = now - (idx * 86400)
        path = "%s/%s/%s" % (archive, station, time.strftime("%Y/%Y_%j", time.gmtime(timestamp)))
        if not os.path.isdir(path):
            print "%s: directory not found" % path
            continue
        count += 1
        for file in os.listdir(path):
            channel = file.split('.')[0]
            parts = channel.split('_')
            if len(parts) == 1:
                loc,chan = ('',parts[0])
            else:
                loc,chan = parts[0:2]
            if chan != "LHZ":
                continue

            if not station_qualities.has_key(channel):
                station_qualities[channel] = []
            series = station_qualities[channel]
            file_name = "%s/%s" % (path, file)
            command = '/bin/bash -c "dumpseed -b 512 %s | grep Quality"' % file_name
            args = shlex.split(command)
            proc = subprocess.Popen(args, stdout=subprocess.PIPE)
            data = proc.stdout.readline()
            reg_quality = re.compile("Quality=(\d+)[%]")
            while data != '':
                match = reg_quality.search(data)
                if match:
                    series.append(int(match.groups()[0]))
                data = proc.stdout.readline()

            proc.wait()

for key in sorted(qualities.keys()):
    print key
    st_qualities = qualities[key]
    if len(st_qualities.keys()) < 1:
        print "  NO CLOCK QUALITY INFO FOR STATION!!"
        continue
    for skey in qualities[key].keys():
        counts = qualities[key][skey]
        total = sum(counts)
        average = float(total) / float(len(counts))
        issue_flag = ""
        if len(counts) < 1000:
            issue_flag = " LOW SAMPLE COUNT!"
        print "  %s - %f [%d data points]%s" % (skey, average, len(counts), issue_flag)

print "Evaluated %d stations." % len(qualities.keys())


