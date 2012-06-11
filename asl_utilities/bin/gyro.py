#!/usr/bin/env python
try:
    from CnC import pyserial
    import Queue
    import datetime
    import math
    import optparse
    import re
    import signal
    import string
    import struct
    import sys
    import threading
    import threading
    import time
    import traceback
except Exception, ex:
    print "[Exception]> %s" % str(ex)
    (ex_f, ex_s, trace) = sys.exc_info()
    traceback.print_tb(trace)

class Gyro:
    def __init__(self):
        self.serial = pyserial.Serial(port=0, baudrate=115200)

        self.syncs = 0
        self.bytes = 0
        self.sync_bytes = 0

        self.c1_invalids = 0
        self.c2_invalids = 0

    def run(self):
        sync_old = -1
        timestamp_offset = 99
        timestamp = None
        last_point = None
        point_sum = 0.0
        while 1:
            if sync_old < 0:
                self.sync()
                self.sync_bytes = 0
                timestamp_offset = 99
                timestamp = None
                last_point = None
                sync_sum = 0.0
                sync_count = 0

                # get first sync value
                data = self.serial.read(6)
                self.bytes += len(data)

                bytes = struct.unpack(">6B", data)
                sync_old = (bytes[0] & 0xc0) >> 6

            data = self.serial.read(6)
            #if platform.system() == "Windows":
            #    current_point = time.clock()
            current_point = time.time()
            timestamp_offset += 1
            if timestamp_offset > 99:
                last_stamp = timestamp
                timestamp = datetime.datetime.now()
                if last_stamp is not None:
                    stamp_diff = timestamp - last_stamp
                    stamp_seconds = float(stamp_diff.microseconds + (stamp_diff.seconds + stamp_diff.days * 24 * 3600) * 10**6) / 10**6
                    difference = point_sum - stamp_seconds
                    print "[%s]>" % last_stamp.strftime("%Y-%m-%d %H:%M:%S.%f")
                    print "[%s]> point_sum=%f stamp_diff=%f (difference=%f)" % (timestamp.strftime("%Y-%m-%d %H:%M:%S.%f"), point_sum, stamp_seconds, difference)
                point_sum = 0.0
                timestamp_offset = 0

            self.bytes += len(data)
            self.sync_bytes += len(data)

            bytes = struct.unpack(">6B", data)
            sync_value = (bytes[0] & 0xc0) >> 6

            if (sync_old == 0) and (sync_value == 1):
                sync_old = sync_value
            elif (sync_old == 1) and (sync_value == 2):
                sync_old = sync_value
            elif (sync_old == 2) and (sync_value == 3):
                sync_old = sync_value
            elif (sync_old == 3) and (sync_value == 0):
                sync_old = sync_value
            else:
                sync_old = -1
                #print "sync broken"
                continue

            #for byte in bytes:
            #	print bin(byte).split('b')[1].rjust(8,"0"),
            #print

            c1_valid = ((bytes[0] & 0x10) >> 4) == 1
            c2_valid = ((bytes[0] & 0x20) >> 5) == 1

            if not c1_valid:
                self.c1_invalids += 1
                sync_old = -1
                continue

            if not c2_valid:
                self.c2_invalids += 1
                sync_old = -1
                continue

            c1 = int(0)
            c2 = int(0)

            c1 |= bytes[5]
            c1 |= bytes[4] << 8
            c1 |= (bytes[3] & 0x3f) << 16
            if c1 & 0x00200000:
                c1 |= 0xffc00000

            c2 |= (bytes[3] & 0xc0) >> 6
            c2 |= bytes[2] << 2
            c2 |= bytes[1] << 10
            c2 |= (bytes[0] & 0x0f) << 18
            if c2 & 0x00200000:
                c2 |= 0xffc00000

            c1, c2 = struct.unpack(">ii", struct.pack(">II", c1, c2))

            # Convert into degrees/second
            f1 = 0.0004768 * c1
            f2 = 0.0004768 * c2

            point_diff_str = ""
            if last_point != None:
                point_sum += current_point - last_point
                point_diff_str = "(%f sec)" % (current_point - last_point,)
            last_point = current_point

            theta = math.atan2((-1.0 * f1),f2) * (180.0 / math.pi) 

            sync_sum += theta
            sync_count += 1

            #print "c1=%+d c2=%+d" % (c1, c2)
            if sync_count > 0:
                avg_str = "AVERAGE=%f" % (sync_sum / sync_count,)
            print "f1=%+f f2=%+f %s > %s THETA=%+0.6f" % (f1, f2, point_diff_str, avg_str, theta)

    def sync(self):
        self.syncs += 1
        print "syncing..."

        sync_map = {
            0 : -1,
            1 : -1,
            2 : -1,
            3 : -1,
            4 : -1,
            5 : -1,
        }

        index = -1 
        while 1:
            index += 1
            if index > 5:
                index = 0

            if len(sync_map) < 1:
                raise Exception("Could not synchronize")
            if len(sync_map) == 1:
                #print "sync index is ", index
                break
            if not sync_map.has_key(index):
                continue

            data = self.serial.read(1)
            self.bytes += len(data)

            byte = struct.unpack(">B", data)[0]
            #print "%08s" % bin(byte).split('b')[1]

            sync_value = (byte & 0xc0) >> 6
            sync_old = sync_map[index]

            if sync_old == -1:
                sync_map[index] = sync_value
                #print "initialized index", index
            elif (sync_old == 0) and (sync_value == 1):
                sync_map[index] = sync_value
            elif (sync_old == 1) and (sync_value == 2):
                sync_map[index] = sync_value
            elif (sync_old == 2) and (sync_value == 3):
                sync_map[index] = sync_value
            elif (sync_old == 3) and (sync_value == 0):
                sync_map[index] = sync_value
            else:
                del sync_map[index]
                #print "eliminated index %d (old=%d new=%d) " % (index, sync_old, sync_value)


if __name__ == "__main__":
    gyro = Gyro()
    try:
        print "opening serial port...",
        gyro.run()
    except KeyboardInterrupt, ex:
        print
    except Exception, ex:
        print "[Exception]> %s" % str(ex)
        (ex_f, ex_s, trace) = sys.exc_info()
        traceback.print_tb(trace)

    print "Read %d bytes (%d since last sync)" % (gyro.bytes, gyro.sync_bytes)
    print "Invalids (c1=%d c2=%d)" % (gyro.c1_invalids, gyro.c2_invalids)
    print "Synchronized %d times" % gyro.syncs
    raw_input("Press Enter...")

