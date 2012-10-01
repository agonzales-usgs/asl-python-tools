#!/usr/bin/env python
import asl

import os
import socket
import struct
import time

from jtk import hexdump


host = "localhost"
port = 7777
socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
socket.connect((host, port))


end = open("/dev/zero", "r").read(512 - 48)

timestamp = time.time()

# record parameters
sequence = -1 
quality = 0
reserved = 0
network = "ZZ"
station = "TOP  "
location = "99"
channel = "TST"

total = 3 #16 * 1024 * 1024
count = 0
while count < total:
    count += 1
    # update the timestamp
    sequence += 1
    if sequence > 999999:
        sequence = 0
    timestamp += 1
    t = time.gmtime(timestamp)

    # pack the structure
    record = struct.pack(">6s1s1s5s2s3s2sHHBBBBHHhhBBBBiHH",
    "%06d" % sequence, # sequence number
    "D",   # quality indicator
    " ",   # reserved
    "TOP", # station
    "99",  # location
    "TST", # channel
    "ZZ",  # network
    t.tm_year,
    t.tm_yday,
    t.tm_hour,
    t.tm_min,
    t.tm_sec,
    0, # reserved
    0, # tenth milliseconds
    1, # samples
    1, # rate factor
    1, # rate multiplier
    0, # activity flags,
    0, # io and clock flags
    0, # data quality flags
    1, # number of blockettes
    0, # time correction
    48, # start of data
    48, # first blockette offset
    ) + end

    print time.strftime("%Y-%m-%d (%j) %H:%M:%S.%%04d", t) % 0
    print hexdump.hexdump(record[:64])
    print "sending..."
    socket.sendall(record)
    print "receiving..."
    data = socket.recv(512)
    print "confirmed."

socket.close()

