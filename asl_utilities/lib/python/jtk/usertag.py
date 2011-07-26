import re

REGEX = re.compile("^[0-9A-Z]{0,6}$")
ALPHA = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

def encode(value):
    if type(value) != str:
        raise TypeError("Bad Type")
    value = value.upper()
    if not REGEX.match(value):
        raise ValueError("Invalid Format")
    if value == "":
        return 0xffffffff
    return int(value, 36)

def decode(value):
    if not isinstance(value, (int, long)):
        raise TypeError("Bad Type")
    value = long(value & 0xffffffff)
    if 0L > value > 2176782335L:
        raise ValueError("Invalid Value")
    if value == 0xffffffff:
        return ""
    result = ""
    while value:
        value, r = divmod(value, 36)
        result = ALPHA[r] + result
    return result or ALPHA[0]
