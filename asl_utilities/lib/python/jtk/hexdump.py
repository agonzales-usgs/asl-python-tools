import struct

def hexdump(bytes, width=16):
    total  = 0
    count  = 0
    string = ""
    result = ""
    for b in map(int, struct.unpack(">%dB" % len(bytes), bytes)):
        if count == 0:
            result += "%08x " % total
        result += " %02x" % b
        if 31 < b < 127:
            string += chr(b)
        else:
            string += '.'
        count += 1
        total += 1
        if (width == 16) and (count == 8): result += " "
        if count == width:
            result += "  |" + string + "|\n"
            count = 0
            string = ""
    end_count = count
    if len(string):
        while count < width:
            count  += 1
            result +=  "   "
        if (width == 16) and (end_count < 8):
            result += " "
        result += "  |" + string + "|\n"
    return result

