#!/usr/bin/env python
import os
import sys

from jtk.StatefulClass import StatefulClass
from jtk.Keys import Keys

class KeyManager(StatefulClass):
    def __init__(self):
        StatefulClass.__init__(self, os.path.abspath(asl.home_directory + '/.keys.db'))
        self.load_state()

        self.keys = Keys()
        self.signatures = Keys()


