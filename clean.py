#!/usr/bin/python
import os
import sys

def clean_dir(directory):
    if os.path.exists(directory):
        entries = os.listdir(directory)
    else:
        raise IOError("%s: no such file or directory" % directory)

    for entry in entries:
        path = "%s/%s" % (directory, entry)
        if (not os.path.islink(path)) and os.path.isdir(path):
            clean_dir(path)
        elif entry[-1:] == '~':
            os.remove(path)
        elif entry[-4:] == '.pyc':
            os.remove(path)
        elif entry[-4:] == '.pyo':
            os.remove(path)
        elif entry[-9:] == '$py.class':
            os.remove(path)
        elif (entry[0] == '.') and (entry[-4:] == '.swp'):
            os.remove(path)

if __name__ == "__main__":
    directory = os.getcwd()
    script = directory + "/" + sys.argv[0].split('/')[-1]
    if os.path.exists(script):
        clean_dir(directory)
