#!/usr/bin/env python
import os
import sys

try:
    import pygtk
    pygtk.require('2.0')
    import gtk
    import gobject
    GTK = True
except:
    GTK = False

def new_icon_gtk(id):
    image_file = os.path.abspath('%s/icons/%s.png' % (path, id))
    if os.path.exists(image_file):
        img = gtk.Image()
        img.set_from_file(image_file)
        return img.get_pixbuf()
    return None

def new_icon_none(id):
    return None

if GTK:
    new_icon = new_icon_gtk
else:
    new_icon = new_icon_none


try:
    home_directory = os.path.abspath(os.environ['HOME'])
except:
    home_directory = os.path.abspath(os.environ['USERPROFILE'])

asl_path_file = os.path.abspath(home_directory + '/.asl_utilities_path')

if not os.path.isfile(asl_path_file):
    print "Could not locate ASL Utilities directory"
    sys.exit(1)
fh = open(asl_path_file, 'r')
path = fh.readline().strip()
if not os.path.exists(path):
    print "ASL Utilities directory '%s' does not exist" % path
    sys.exit(1)
if not os.path.isdir(path):
    print "path '%s' exists, but is not a direcotry" % path
    sys.exit(1)

python_path = os.path.abspath(path + '/lib/python')

sys.path.insert(0, python_path)

