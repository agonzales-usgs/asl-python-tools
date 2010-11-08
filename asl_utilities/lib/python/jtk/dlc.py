#!/usr/bin/python
import base64
import os
import re
import string
import struct
import sys
import time

enc64 = lambda d: base64.urlsafe_b64encode( d )
dec64 = lambda d: base64.urlsafe_b64decode( d )

regex = re.compile('(\w+) (\d{2})[/]([^ ]{3}) Span ([^ ]+) to ([^ ]+) (\d+) records, start index (\d+)(?:, ([-]?\d+) tms gap)?')

def compact(text):
    return enc64(_compact(text))

def _compact(text):
    results = ''
    matches = regex.findall(text)
    for (name, location, channel, time_start, time_end, records, index, gap) in matches:
        format = '5sB3siHiHII'
        result = ''
        result = struct.pack(format, padded(name,5), int(location), channel,
                    int(time.mktime(time.strptime(time_start[:-5], "%Y,%j,%H:%M:%S"))),
                    int(time_start[-4:]),
                    int(time.mktime(time.strptime(time_end[:-5], "%Y,%j,%H:%M:%S"))),
                    int(time_end[-4:]),
                    int(records), int(index))
        results += result
    return results


def expand(buffer):
    return _expand(dec64(buffer))

def _expand(buffer):
    format = '5sB3siHiHII'
    struct_len = struct.calcsize(format)
    buffer_len = len(buffer)
    results = []
    start = 0
    end = 0
    while buffer_len - start >= struct_len:
        end = start + struct_len
        result = struct.unpack(format, buffer[start:end])
        result = (result[0].strip(),) + result[1:]
        results.append(result)
        start += struct_len
    return results

def padded(string, max):
    while len(string) < max:
        string += ' '
    return string


if __name__ == '__main__':
    if os.popen('which dlutil').read():
        text = os.popen('dlutil ' + ' '.join(sys.argv[1:])).read()
        compacted = compact(text)
        sys.stdout.write(compacted)
        sys.stdout.flush()

