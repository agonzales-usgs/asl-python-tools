#!/usr/bin/env python
import PythonMagick
import os

files = os.listdir('.')

for file in files:
    if file[-4:] != '.png':
        print "skipping", file
        continue
    ico = file[:-4] + '.ico'
    print "convert", file, "->", ico
    img = PythonMagick.Image()
    img.read(file)
    img.write(ico)
