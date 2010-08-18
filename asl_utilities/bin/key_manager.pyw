#!/usr/bin/env python
import asl

import os
import re
import struct
import subprocess
import sys
import threading
import time

import pygtk
pygtk.require('2.0')
import gtk
import gobject
gobject.threads_init()

from jtk.StatefulClass import StatefulClass
from jtk.Keys import Keys

class KeyManager(StatefulClass):
    def __init__(self):
        StatefulClass.__init__(self, os.path.abspath(asl.home_directory + '/.keys.db'))
        self.load_state()

        self.keys = Keys()
        self.signatures = Keys()


    
