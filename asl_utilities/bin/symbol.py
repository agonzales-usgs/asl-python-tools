#!/usr/bin/env python
import asl

import glob
import inspect
import optparse
import os
import Queue
import re
import stat
import struct
import sys
import threading

import pyserial

HAS_GUI=True
try:
    import pygtk
    pygtk.require('2.0')
    import gtk
    import gobject
    gobject.threads_init()
except:
    HAS_GUI=False
    pass

crc_table = [
0x0000, 0xC0C1, 0xC181, 0x0140, 0xC301, 0x03C0, 0x0280, 0xC241,
0xC601, 0x06C0, 0x0780, 0xC741, 0x0500, 0xC5C1, 0xC481, 0x0440,
0xCC01, 0x0CC0, 0x0D80, 0xCD41, 0x0F00, 0xCFC1, 0xCE81, 0x0E40,
0x0A00, 0xCAC1, 0xCB81, 0x0B40, 0xC901, 0x09C0, 0x0880, 0xC841,
0xD801, 0x18C0, 0x1980, 0xD941, 0x1B00, 0xDBC1, 0xDA81, 0x1A40,
0x1E00, 0xDEC1, 0xDF81, 0x1F40, 0xDD01, 0x1DC0, 0x1C80, 0xDC41,
0x1400, 0xD4C1, 0xD581, 0x1540, 0xD701, 0x17C0, 0x1680, 0xD641,
0xD201, 0x12C0, 0x1380, 0xD341, 0x1100, 0xD1C1, 0xD081, 0x1040,
0xF001, 0x30C0, 0x3180, 0xF141, 0x3300, 0xF3C1, 0xF281, 0x3240,
0x3600, 0xF6C1, 0xF781, 0x3740, 0xF501, 0x35C0, 0x3480, 0xF441,
0x3C00, 0xFCC1, 0xFD81, 0x3D40, 0xFF01, 0x3FC0, 0x3E80, 0xFE41,
0xFA01, 0x3AC0, 0x3B80, 0xFB41, 0x3900, 0xF9C1, 0xF881, 0x3840,
0x2800, 0xE8C1, 0xE981, 0x2940, 0xEB01, 0x2BC0, 0x2A80, 0xEA41,
0xEE01, 0x2EC0, 0x2F80, 0xEF41, 0x2D00, 0xEDC1, 0xEC81, 0x2C40,
0xE401, 0x24C0, 0x2580, 0xE541, 0x2700, 0xE7C1, 0xE681, 0x2640,
0x2200, 0xE2C1, 0xE381, 0x2340, 0xE101, 0x21C0, 0x2080, 0xE041,
0xA001, 0x60C0, 0x6180, 0xA141, 0x6300, 0xA3C1, 0xA281, 0x6240,
0x6600, 0xA6C1, 0xA781, 0x6740, 0xA501, 0x65C0, 0x6480, 0xA441,
0x6C00, 0xACC1, 0xAD81, 0x6D40, 0xAF01, 0x6FC0, 0x6E80, 0xAE41,
0xAA01, 0x6AC0, 0x6B80, 0xAB41, 0x6900, 0xA9C1, 0xA881, 0x6840,
0x7800, 0xB8C1, 0xB981, 0x7940, 0xBB01, 0x7BC0, 0x7A80, 0xBA41,
0xBE01, 0x7EC0, 0x7F80, 0xBF41, 0x7D00, 0xBDC1, 0xBC81, 0x7C40,
0xB401, 0x74C0, 0x7580, 0xB541, 0x7700, 0xB7C1, 0xB681, 0x7640,
0x7200, 0xB2C1, 0xB381, 0x7340, 0xB101, 0x71C0, 0x7080, 0xB041,
0x5000, 0x90C1, 0x9181, 0x5140, 0x9301, 0x53C0, 0x5280, 0x9241,
0x9601, 0x56C0, 0x5780, 0x9741, 0x5500, 0x95C1, 0x9481, 0x5440,
0x9C01, 0x5CC0, 0x5D80, 0x9D41, 0x5F00, 0x9FC1, 0x9E81, 0x5E40,
0x5A00, 0x9AC1, 0x9B81, 0x5B40, 0x9901, 0x59C0, 0x5880, 0x9841,
0x8801, 0x48C0, 0x4980, 0x8941, 0x4B00, 0x8BC1, 0x8A81, 0x4A40,
0x4E00, 0x8EC1, 0x8F81, 0x4F40, 0x8D01, 0x4DC0, 0x4C80, 0x8C41,
0x4400, 0x84C1, 0x8581, 0x4540, 0x8701, 0x47C0, 0x4680, 0x8641,
0x8201, 0x42C0, 0x4380, 0x8341, 0x4100, 0x81C1, 0x8081, 0x4040
]

class CRC:
    def __init__(self):
        self.reset()

    def reset(self):
        self.lo  = 0xFF
        self.hi  = 0xFF

    def add(self, string):
        values = struct.unpack(">%dB" % len(string))
        for v in values:
            tmp = (self.hi & 0xFF) ^ (crc_table[((self.lo & 0xFF) ^ v) & 0xFF])
            self.hi = (tmp >> 8) & 0xFF
            self.lo = tmp & 0xFF

    def getCRC(self):
        return (self.lo & 0xFF) | ((self.hi & 0xFF) << 8)


# === PARAMETERS ========
def conv2of5(L1, L2):
    result = {"type": None}
    if L2 == 0:
        result["type"] = 'one'
        result["value"] = L1
    elif L1 > L2:
        result["type"] = 'two'
        result["value"] = (L1, L2)
    elif L1 < L2:
        result["type"] = 'range'
        result["value"] = (L1, L2)
    elif L1 == 0 and L2 == 0:
        result["type"] = 'any'

    return result

parameters = {
    # Decode Controls
    0x1f : {
        "name": "Code 39",
        "hint": "",
        "values": {
            0: "Disabled",
            1: "Enabled"
        },
        "default": 1},
    0x09 : {
        "name": "UPC",
        "hint": "",
        "values": {
            0: "Disabled",
            1: "Enabled"
        },
        "default": 1},
    0x08 : {
        "name": "Code128",
        "hint": "",
        "values": {
            0: "Disabled",
            1: "Enabled"
        },
        "default": 1},
    0x36 : {
        "name": "Code 39 Full ASCII",
        "hint": "",
        "values": {
            0: "Disabled",
            1: "Enabled"
        },
        "default": 0},
    0x35 : {
        "name": "UPC Supps",
        "hint": "",
        "values": {
            0: "No Supps",
            1: "Supps only",
            2: "Auto-D"
        },
        "default": 2},
    0x29 : {
        "name": "Convert UPC E to A",
        "hint": "",
        "values": {
            0: "Disabled",
            1: "Enabled"
        },
        "default": 0},
    0x2a : {
        "name": "Convert EAN8 to EAN13",
        "hint": "",
        "values": {
            0: "Disabled",
            1: "Enabled"
        },
        "default": 0},
    0x37 : {
        "name": "Convert EAN8 to EAN13 Type",
        "hint": "Set code type of converted EAN8 barcode to EAN8 or EAN13",
        "values": {
            0: "Disabled",
            1: "Enabled"
        },
        "default": 0},
    0x2b : {
        "name": "Send UPC A Check Digit",
        "hint": "",
        "values": {
            0: "Disabled",
            1: "Enabled"
        },
        "default": 1},
    0x2c : {
        "name": "Send UPC E Check Digit",
        "hint": "",
        "values": {
            0: "Disabled",
            1: "Enabled"
        },
        "default": 1},
    0x2e : {
        "name": "Code 39 Check Digit",
        "hint": "",
        "values": {
            0: "Disabled",
            1: "Enabled"
        },
        "default": 0},
    0x2d : {
        "name": "Xmit Code 39 Check Digit",
        "hint": "",
        "values": {
            0: "Disabled",
            1: "Enabled"
        },
        "default": 0},
    0x25 : {
        "name": "UPCE_Preamble",
        "hint": "",
        "values": {
            0: "None",
            1: "System char",
            2: "Sys char & country code"
        },
        "default": 1},
    0x24 : {
        "name": "UPCA_Preamble",
        "hint": "",
        "values": {
            0: "None",
            1: "System char",
            2: "Sys char & country code"
        },
        "default": 1},
    0x34 : {
        "name": "EAN 128",
        "hint": "",
        "values": {
            0: "Disabled",
            1: "Enabled"
        },
        "default": 1},
    0x38 : {
        "name": "Coupon Code",
        "hint": "",
        "values": {
            0: "Disabled",
            1: "Enabled"
        },
        "default": 1},
    0x3a : {
        "name": "I 2of5",
        "hint": "",
        "values": {
            0: "Disabled",
            1: "Enabled"
        },
        "default": 1},
    0x41 : {
        "name": "I 2of5 Check Digit",
        "hint": "",
        "values": {
            0: "Disabled",
            1: "USS check digit",
            2: "OPCC check digit"
        },
        "default": 0},
    0x40 : {
        "name": "Xmit I 2of5 Check Digit",
        "hint": "",
        "values": {
            0: "Disabled",
            1: "Enabled"
        },
        "default": 0},
    0x3f : {
        "name": "Convert ITF14 to EAN 13",
        "hint": "",
        "values": {
            0: "Disabled",
            1: "Enabled"
        },
        "default": 0},
    0x3b : {
        "name": "I 2of5 Length 1",
        "hint": "One Discrete Length, Two Discrete Lengths, Length Within Range, or Any Length",
        "values": {
            "converter": conv2of5,
            "associate": 0x3c,
        },
        "default": 14},
    0x3c : {
        "name": "I 2of5 Length 2",
        "hint": "One Discrete Length, Two Discrete Lengths, Length Within Range, or Any Length",
        "values": {
            "converter": conv2of5,
            "associate": 0x3b,
        },
        "default": 0},
    0x39 : {
        "name": "D 2of5",
        "hint": "",
        "values": {
            0: "Disabled",
            1: "Enabled"
        },
        "default": 0},
    0x3d : {
        "name": "D 2of5 Length 1",
        "hint": "One Discrete Length, Two Discrete Lengths, Length Within Range, or Any Length",
        "values": {
            "converter": conv2of5,
            "associate": 0x3e,
        },
        "default": 12},
    0x3e : {
        "name": "D 2of5 Length 2",
        "hint": "One Discrete Length, Two Discrete Lengths, Length Within Range, or Any Length",
        "values": {
            "converter": conv2of5,
            "associate": 0x3d,
        },
        "default": 0},
    0x2f : {
        "name": "UPC/EAN Security Level",
        "hint": "",
        "values": {
            "range": True,
            "min":   0,
            "max":   3,
            "step":  1,
            "adjust": 1
        },
        "default": 0},
    0x30 : {
        "name": "UPC/EAN Supplemental Redundancy (No_supp_max)",
        "hint": "Number of times to decode UPC/EAN barcode without supplements",
        "values": {
            "range": True,
            "min":   2,
            "max":   20,
            "step":  1,
            "adjust": 1
        },
        "default": 5},

    # Scanner Controls
    0x11 : {
        "name": "Scanner On-Time",
        "hint": "",
        "values": {
            "range": True,
            "min":   1000,
            "max":   10000,
            "step":  100,
            "adjust": .01,
            "units": "seconds"
        },
        "default": 3000},
    0x02 : {
        "name": "Volume",
        "hint": "",
        "values": {
            0: "Off",
            1: "On"
        },
        "default": 1},
    0x20 : {
        "name": "Comm Awake Time",
        "hint": "How long scanner will stay awake for host communication",
        "values": {
            "range": True,
            "min":   1,
            "max":   6,
            "step":  1,
            "adjust": 20,
            "units": "seconds"
        },
        "default": 1},
    0x0d : {
        "name": "Baud Rate",
        "hint": "",
        "values": {
            3: 300,
            4: 600,
            5: 1200,
            6: 2400,
            7: 4800,
            8: 9600,
            9: 19200
        },
        "default": 8},
    0x1d : {
        "name": "Baud Switch Delay",
        "hint": "How long scanner will delay before sending a response to a new baud rate command",
        "values": {
            "range": True,
            "min":   0.0,
            "max":   1000.0,
            "step":  10.0,
            "adjust": 1000.0,
            "units": "seconds"
        },
        "default": 35},
    0x1c : {
        "name": "Reset Baud Rates",
        "hint": "Determines if default baud rate will be used on power-up",
        "values": {
            0: "Disabled",
            1: "Enabled"
        },
        "default": 1},
    0x04 : {
        "name": "Reject Redundant Barcode",
        "hint": "Disabling will allow same barcode to be stored consecutively",
        "values": {
            0: "Disabled",
            1: "Enabled"
        },
        "default": 0},
    0x0a : {
        "name": "Host Connect Beep",
        "hint": "",
        "values": {
            0: "Disabled",
            1: "Enabled"
        },
        "default": 1},
    0x0b : {
        "name": "Host Complete Beep",
        "hint": "",
        "values": {
            0: "Disabled",
            1: "Enabled"
        },
        "default": 1},
    0x07 : {
        "name": "Low-Battery Indication",
        "hint": "Detemines how low battery condition will be handled",
        "values": {
            0: "No Indication/No Operation",
            1: "No Indication/Allow Operation",
            2: "Indicate/No Operation",
            3: "Indicate/Allow Operation"
        },
        "default": 3},
    0x0f : {
        "name": "Auto_Clear",
        "hint": "Clear barcodes after upload",
        "values": {
            0: "Disabled",
            1: "Enabled"
        },
        "default": 0},
    0x21 : {
        "name": "Delete_Enable",
        "hint": "Determines operation of delete and clear all functions",
        "values": {
            0: "Delete Disabled/Clear All Disabled",
            1: "Delete Disabled/Clear All Enabled",
            2: "Delete Enabled/Clear All Disabled",
            3: "Delete Enabled/Clear All Enabled",
            4: "Radio Stamp",
            5: "VDIU Voluntary Device Initiated Upload"
        },
        "default": 3},
    0x31 : {
        "name": "Data Protection",
        "hint": "",
        "values": {
            0: "Disabled",
            1: "Enabled"
        },
        "default": 0},
    0x32 : {
        "name": "Memory Full Indication",
        "hint": "",
        "values": {
            0: "Disabled",
            1: "Enabled"
        },
        "default": 1},
    0x33 : {
        "name": "Memory Low Indication",
        "hint": "EEPROM is 90% full",
        "values": {
            0: "Disabled",
            1: "Enabled"
        },
        "default": 0},
    0x22 : {
        "name": "Max Barcode Len",
        "hint": "Increase to 30 for Coupon Code",
        "values": {
            "range": True,
            "min":   1,
            "max":   30,
            "step":  1,
            "adjust": 1,
            "units":  "characters"
        },
        "default": 30},
    0x1e : {
        "name": "Good Decode LED On Time",
        "hint": "",
        "values": {
            "range": True,
            "min":   250,
            "max":   1000,
            "step":  250,
            "adjust": 1,
            "units":  "milliseconds"
        },
        "default": 4},
    0x23 : {
        "name": "Store_RTC",
        "hint": "Store Real Time Clock data",
        "values": {
            0: "Disabled",
            1: "Enabled"
        },
        "default": 1},
    0x4f : {
        "name": "ASCII mode",
        "hint": "Allow user to choose how unencrypted data is to be sent",
        "values": {
            0: "Like encrypted data (CS-1504 Mode)",
            1: "As ASCII strings (like CS-2000)"
        },
        "default": 0},
    0x55 : {
        "name": "Beeper Toggle",
        "hint": "Allows user to toggle beeper On/Off with the scan key",
        "values": {
            0: "No",
            1: "Yes"
        },
        "default": 1},
    0x56 : {
        "name": "Beeper Auto On",
        "hint": "Automatically turns on a beeper toggled off by the scan key after 8 hours",
        "values": {
            0: "No",
            1: "Yes"
        },
        "default": 0},
    0x26 : {
        "name": "Scratch Pad",
        "hint": "A 32 byte storage area (unused by the CS-1504) for customer use",
        "values": {
            "string": True,
            "length": 32
        },
        "default": None},
}

# === COMMANDS ==========
CMD_INTERROGATE         =  1
CMD_CLEAR_BAR_CODES     =  2
CMD_DOWNLOAD_PARAMETERS =  3
CMD_SPECIAL             =  4
CMD_POWER_DOWN          =  5
CMD_UPLOAD_BARCODE_DATA =  7
CMD_UPLOAD_PARAMETERS   =  8
CMD_SET_TIME            =  9
CMD_GET_TIME            = 10

class Command(object):
    def __init__(self, command, strings):
        object.__init__(self)
        self.command = command
        self.stx     = 0x2
        self.strings = strings
        self.message = None

    def build(self):
        self.message = struct.pack(">BB", self.command, self.stx)
        for string in self.strings:
            self.message += struct.pack(">B%ds" % len(string), string)
        self.message += struct.pack(">B", 0)
        crc = CRC()
        crc.add(self.message)
        self.message += struct.pack(">H", crc.getCRC())


RSP_BAD_STRUCTURE = -3
RSP_BAD_CRC       = -2
RSP_BAD_STX       = -1
RSP_UNSUPPORTED   =  5
RSP_OK            =  6
RSP_CMD_CRC_ERR   =  7
RSP_RCV_CHAR_ERR  =  8
RSP_GENERAL_ERR   =  9

status_map = {
    RSP_BAD_CRC      : "Bad Structure",
    RSP_BAD_CRC      : "Bad CRC Value",
    RSP_BAD_STX      : "Bad STX Value",
    RSP_UNSUPPORTED  : "Unsupported Command Number",
    RSP_OK           : "Okay",
    RSP_CMD_CRC_ERR  : "Command CRC Error",
    RSP_RCV_CHAR_ERR : "Received Character Error",
    RSP_GENERAL_ERR  : "General Error",
}


class Response(object):
    def __init__(self, message):
        object.__init__(self)
        self.status  = None
        self.data    = None
        self.strings = []

        crc = CRC()

        self.status = struct.unpack(">B", message[:1])[0]
        if self.status != RSP_OK:
            return
        stx = struct.unpack(">B", message[1:2])[0]
        if stx != 0x2:
            self.status = RSP_BAD_STX
            return
        crc = struct.unpack(">H", message[-2:])[0]
        crc.add(message[:-2])
        if stx != 0x2:
            self.status = RSP_BAD_STX
            return
        term = struct.unpack(">H", message[-2:-1])[0]
        if term != 0:
            self.status = RSP_BAD_STRUCTURE
            return

        rem = message[2:]
        count = struct.unpack(">B", rem[0:1])[0]
        while count:
            self.strings.append(">%ds" % count, rem[1:1+count])[0]
            rem = rem[1+count:]
            count = struct.unpack(">B", rem[0:1])[0]

    def okay(self):
        return self.status == RSP_OK

    def error_str(self):
        try:
            return status_map[self.status]
        except KeyError:
            return "Unrecognized Status"


# === CommThread Class /*{{{*/
class CommThread(threading.Thread):
    def __init__(self, parent):
        threading.Thread.__init__(self)
        self.daemon  = True
        self.parent  = parent
        self.queue   = Queue.Queue()
        self.running = False
        self.cancelled = False

        self.args    = {
            "port"      : 0,
            "baudrate"  : 9600,
            "bytesize"  : pyserial.serialutil.EIGHTBITS,
            "parity"    : pyserial.serialutil.PARITY_ODD,
            "stopbits"  : pyserial.serialutil.STOPBITS_ONE,
            "rtscts"    : True,
        }

    def halt(self):
        self.running = False
        self.notify()

    def notify(self):
        self.queue.put(("HALT",None))

    def cancel(self):
        self.cancelled = True

    def run(self):
        self.running = True
        self.connect()
        while self.running:
            try:
                self.cancelled = False
                cmd,data = self.queue.get()
                if cmd == "GET-STATUS":
                    self.get_status()
                if cmd == "READ-CODES":
                    self.read_codes()
                if cmd == "CLEAR-CODES":
                    self.clear_codes()
                if cmd == "POWER-DOWN":
                    self.power_down()
                if cmd == "READ-CONFIG":
                    self.read_config()
                if cmd == "WRITE-CONFIG":
                    self.write_config()
                if cmd == "GET-TIME":
                    self.get_time()
                if cmd == "SET-TIME":
                    self.set_time()
            except Queue.Empty:
                pass
            except KeyboardInterrupt:
                pass
            except:
                pass

    def get_status(self):
        command = Command(CMD_INTERROGATE, )

    def read_codes(self):
        command = Command(CMD_UPDLOAD_BARCODE_DATA, )

    def clear_codes(self):
        command = Command(CMD_CLEAR_BAR_CODES, )

    def power_down(self):
        command = Command(CMD_POWER_DOWN, )

    def read_config(self):
        command = Command(CMD_UPLOAD_PARAMETERS, )

    def write_config(self):
        command = Command(CMD_DOWNLOAD_PARAMETERS, )

    def get_time(self):
        command = Command(CMD_GET_TIME, )

    def set_time(self):
        command = Command(CMD_SET_TIME, )

    def connect(self):
        # detect platform first...
        if self.platform == 'win32':
            self.port = pyserial.serialwin32.Win32Serial(**self.args)
        else:
            self.port = pyserial.serialposix.PosixSerial(**self.args)

#/*}}}*/
        
# === CalsUI Class (GTK+ Graphical Interface) /*{{{*/
class SymbolUI:
    def __init__(self):
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title("Motorola Symbol")
        self.window.set_icon(asl.new_icon('barcode'))

# ===== Widget Creation ============================================
        self.vbox_main = gtk.VBox()

        self.hbox_verbosity = gtk.HBox()
        self.hbox_records   = gtk.HBox()
        self.hbox_types     = gtk.HBox()
        self.hbox_report    = gtk.HBox()
        self.hbox_stdout    = gtk.HBox()
        self.hbox_display   = gtk.HBox()
        self.hbox_control   = gtk.HBox()

      # User Interaction Widgets
        self.checkbutton_succinct = gtk.CheckButton(label="Succinct")
        self.label_verbosity = gtk.Label("Verbosity")
        self.adjustment_verbosity = gtk.Adjustment(value=0, lower=0, upper=2**64, step_incr=1, page_incr=5, page_size=1)
        self.spinbutton_verbosity = gtk.SpinButton(self.adjustment_verbosity)

        self.checkbutton_circular = gtk.CheckButton(label="Files are Circular Buffers")
        self.label_num_records = gtk.Label("Max Records")
        self.adjustment_num_records = gtk.Adjustment(value=0, lower=0, upper=2**64, step_incr=1, page_incr=256, page_size=1)
        self.spinbutton_num_records = gtk.SpinButton(self.adjustment_num_records)

        self.checkbutton_unknowns = gtk.CheckButton(label="Display Non-Cal. Blockettes")
        self.checkbutton_report = gtk.CheckButton(label="Report File Names")
        self.checkbutton_stdout = gtk.CheckButton(label="Print to Console (stdout)")

        self.textbuffer_display = gtk.TextBuffer()
        self.textview_display   = gtk.TextView(buffer=self.textbuffer_display)
        self.scrolledwindow_display = gtk.ScrolledWindow()
        self.scrolledwindow_display.add(self.textview_display)

        self.button_files = gtk.Button(stock=None, use_underline=True)
        self.hbox_files   = gtk.HBox()
        self.image_files  = gtk.Image()
        self.image_files.set_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_MENU)
        self.label_files  = gtk.Label('Select Files')
        self.button_files.add(self.hbox_files)
        self.hbox_files.pack_start(self.image_files, padding=1)
        self.hbox_files.pack_start(self.label_files, padding=1)

        self.button_find = gtk.Button(stock=None, use_underline=True)
        self.hbox_find   = gtk.HBox()
        self.image_find  = gtk.Image()
        self.image_find.set_from_stock(gtk.STOCK_ZOOM_IN, gtk.ICON_SIZE_MENU)
        self.label_find  = gtk.Label('Find Cals')
        self.button_find.add(self.hbox_find)
        self.hbox_find.pack_start(self.image_find, padding=1)
        self.hbox_find.pack_start(self.label_find, padding=1)

        self.button_copy = gtk.Button(stock=None, use_underline=True)
        self.hbox_copy   = gtk.HBox()
        self.image_copy  = gtk.Image()
        self.image_copy.set_from_stock(gtk.STOCK_COPY, gtk.ICON_SIZE_MENU)
        self.label_copy  = gtk.Label('Copy')
        self.button_copy.add(self.hbox_copy)
        self.hbox_copy.pack_start(self.image_copy, padding=1)
        self.hbox_copy.pack_start(self.label_copy, padding=1)

        self.button_cancel = gtk.Button(stock=None, use_underline=True)
        self.hbox_cancel   = gtk.HBox()
        self.image_cancel  = gtk.Image()
        self.image_cancel.set_from_stock(gtk.STOCK_CANCEL, gtk.ICON_SIZE_MENU)
        self.label_cancel  = gtk.Label('Cancel')
        self.button_cancel.add(self.hbox_cancel)
        self.hbox_cancel.pack_start(self.image_cancel, padding=1)
        self.hbox_cancel.pack_start(self.label_cancel, padding=1)

        self.button_quit = gtk.Button(stock=None, use_underline=True)
        self.hbox_quit   = gtk.HBox()
        self.image_quit  = gtk.Image()
        self.image_quit.set_from_stock(gtk.STOCK_QUIT, gtk.ICON_SIZE_MENU)
        self.label_quit  = gtk.Label('Quit')
        self.button_quit.add(self.hbox_quit)
        self.hbox_quit.pack_start(self.image_quit, padding=1)
        self.hbox_quit.pack_start(self.label_quit, padding=1)

# ===== Layout Configuration =======================================
        self.window.add(self.vbox_main)
        self.window.set_size_request(550, 300)

        self.vbox_main.pack_start(self.hbox_verbosity, False, True,  0)
        self.vbox_main.pack_start(self.hbox_records,   False, True,  0)
        self.vbox_main.pack_start(self.hbox_types,     False, True,  0)
        self.vbox_main.pack_start(self.hbox_report,    False, True,  0)
        self.vbox_main.pack_start(self.hbox_stdout,    False, True,  0)
        self.vbox_main.pack_start(self.hbox_display,   True,  True,  0)
        self.vbox_main.pack_start(self.hbox_control,   False, True,  0)

        self.hbox_verbosity.pack_start(self.checkbutton_succinct, False, False, 0)
        self.hbox_verbosity.pack_end(self.spinbutton_verbosity, False, False, 0)
        self.hbox_verbosity.pack_end(self.label_verbosity, False, False, 0)

        self.hbox_records.pack_start(self.checkbutton_circular, False, False, 0)
        self.hbox_records.pack_end(self.spinbutton_num_records, False, False, 0)
        self.hbox_records.pack_end(self.label_num_records, False, False, 0)

        self.hbox_types.pack_start(self.checkbutton_unknowns, False, False, 0)

        self.hbox_report.pack_start(self.checkbutton_report, False, False, 0)

        self.hbox_stdout.pack_start(self.checkbutton_stdout, False, False, 0)

        self.hbox_display.pack_start(self.scrolledwindow_display, True, True, 0)

        self.hbox_control.pack_start(self.button_files, False, False, 0)
        self.hbox_control.pack_start(self.button_find,  False, False, 0)
        self.hbox_control.pack_start(self.button_copy,  False, False, 0)
        self.hbox_control.pack_end(self.button_quit,    False, False, 0)
        self.hbox_control.pack_end(self.button_cancel,  False, False, 0)

# ===== Widget Configurations ======================================
        self.checkbutton_succinct.set_active(False)
        self.spinbutton_verbosity.set_value(0)
        self.checkbutton_circular.set_active(False)
        self.spinbutton_num_records.set_value(0)
        self.checkbutton_unknowns.set_active(False)
        self.checkbutton_report.set_active(False)
        self.checkbutton_stdout.set_active(False)
        self.textbuffer_display.set_text('')
        self.textview_display.set_editable(False)
        self.button_find.set_sensitive(False)
        self.button_copy.set_sensitive(False)
        self.button_cancel.set_sensitive(False)

# ===== Hidden Objects =============================================
        self.clipboard = gtk.Clipboard()

# ===== Signal Bindings ============================================

# ===== Event Bindings =============================================
        self.window.connect("destroy-event", self.callback_quit, None)
        self.window.connect("delete-event",  self.callback_quit, None)

        self.button_files.connect("clicked", self.callback_files, None)
        self.button_find.connect("clicked", self.callback_find, None)
        self.button_copy.connect("clicked", self.callback_copy, None)
        self.button_cancel.connect("clicked", self.callback_cancel, None)
        self.button_quit.connect("clicked", self.callback_quit, None)

        self.window.connect("key-press-event", self.callback_key_pressed)

      # Show widgets
        self.window.show_all()

      # Hidden Buttons (Used for Threaded GUI update)
        self.hbutton_refresh_display = gtk.Button()
        self.hbutton_refresh_display.connect('clicked', self.callback_refresh_display, None)

        self.files  = []
        self.log_queue = Queue.Queue()
        self.comm_thread = CommThread(self)
        self.comm_thread.start()

# ===== Callbacks ==================================================
    def callback_key_pressed(self, widget, event, data=None):
        if event.state == gtk.gdk.MOD1_MASK:
            if event.keyval == ord('q'):
                self.callback_quit(widget, event, data)
            elif event.keyval == ord('c'):
                if not (self, self.button_copy.state & gtk.STATE_INSENSITIVE):
                    self.text_to_clipboard()
            elif event.keyval == ord('f'):
                if not (self, self.button_find.state & gtk.STATE_INSENSITIVE):
                    self.callback_find(widget, event, data)
            elif event.keyval == ord('s'):
                self.select_files()
            elif event.keyval == ord('x'):
                self.cancel()
            self.update_interface()
                
    def callback_quit(self, widget, event, data=None):
        self.cancel()
        self.thread_writer.halt()
        self.close_application(widget, event, data)

    def callback_files(self, widget, event, data=None):
        self.select_files()
        self.update_interface()

    def callback_find(self, widget, event, data=None):
        self.find()
        self.update_interface()

    def callback_copy(self, widget, event, data=None):
        self.text_to_clipboard()

    def callback_cancel(self, widget, event, data=None):
        self.cancel()

    def callback_refresh_display(self, widget, event, data=None):
        try:
            while 1:
                command,message = self.log_queue.get_nowait()
                if command == "CLEAR":
                    self.textbuffer_display.set_text("")
                elif command == "APPEND":
                    self.textbuffer_display.insert_at_cursor(message)
                elif command == "SET":
                    self.textbuffer_display.set_text(message)
        except Queue.Empty:
            pass

# ===== Methods ====================================================
    def update_interface(self):
        if len(self.files):
            self.button_find.set_sensitive(True)
        else:
            self.button_find.set_sensitive(False)

        if self.textbuffer_display.get_char_count() > 0:
            self.button_copy.set_sensitive(True)
        else:
            self.button_copy.set_sensitive(False)

        if self.reader.is_running():
            self.button_cancel.set_sensitive(True)
        else:
            self.button_cancel.set_sensitive(False)

    def cancel(self):
        if self.reader.is_running():
            self.thread_reader.halt()
    
    def text_to_clipboard(self):
        s,e = self.textbuffer_display.get_bounds()
        self.clipboard.set_text(self.textbuffer_display.get_text(s,e))

    def close_application(self, widget, event, data=None):
        gtk.main_quit()
        return False

    def select_files(self):
        dir = ""
        for file in self.files:
            dir = self.dir_from_file_path(file)
            if os.path.isdir(dir):
                break
            dir = ""
        self.files = []
        file_chooser = gtk.FileChooserDialog("Select Log File", None,
                                             gtk.FILE_CHOOSER_ACTION_OPEN,
                                             (gtk.STOCK_CANCEL,
                                              gtk.RESPONSE_CANCEL,
                                              gtk.STOCK_OPEN,
                                              gtk.RESPONSE_OK))
        file_chooser.set_default_response(gtk.RESPONSE_OK)
        if dir and len(dir):
            file_chooser.set_current_folder(dir)
        file_chooser.set_select_multiple(True)
        result = file_chooser.run()
        if result == gtk.RESPONSE_OK:
            self.thread_writer.clear()
            self.textbuffer_display.set_text('')
            self.files = file_chooser.get_filenames()
        file_chooser.destroy()

    def dir_from_file_path(self, file):
        dir = ""
        dir_parts = file.rsplit("/", 1)
        if len(dir_parts) != 2:
            dir_parts = file.rsplit("\\", 1)
        if len(dir_parts):
            dir = dir_parts[0]
        return dir

    def find(self):
        self.textbuffer_display.set_text('')

        self.reader.succinct = False
        if self.checkbutton_succinct.get_active():
            self.reader.succinct = True

        self.reader.verbosity = self.spinbutton_verbosity.get_value()

        self.reader.print_unknowns = False
        if self.checkbutton_unknowns.get_active():
            self.reader.print_unknowns = True

        self.reader.circular = False
        if self.checkbutton_circular.get_active():
            self.reader.circular = True

        self.reader.num_records = self.spinbutton_num_records.get_value()
        self.reader.report_file_names = self.checkbutton_report.get_active()

        self.thread_writer.to_stdout(False)
        if self.checkbutton_stdout.get_active():
            self.thread_writer.to_stdout(True)

        self.reader.clear_files()
        if len(self.files):
            self.reader.add_files(self.files)

        self.thread_reader = ReadThread()
        self.thread_reader.set_reader(self.reader)
        self.thread_reader.start()
#/*}}}*/

# === main /*{{{*/
def main():
    reader = None
    try:
        option_list = []
        #option_list.append(optparse.make_option("-c", "--circular-buffer", dest="circular", action="store_true", help="files should be treated as circular buffers with matching idx file"))
        option_list.append(optparse.make_option("-g", "--gui", dest="gui", action="store_true", help="launch in graphical mode"))
        #option_list.append(optparse.make_option("-n", "--number-of-records", dest="numrecs", type="int", action="store", help="maximum number of SEED records to read"))
        #option_list.append(optparse.make_option("-r", "--report-file-names", action="store_true", dest="report_file_names", help="report the name of each valid file"))
        #option_list.append(optparse.make_option("-s", "--succinct", action="store_true", dest="succinct", help="print one line per blockette"))
        #option_list.append(optparse.make_option("-u", "--print-unknowns", action="store_true", dest="unknowns", help="print types of found non-calibration blockettes"))
        option_list.append(optparse.make_option("-v", action="count", dest="verbosity", help="specify multiple time to increase verbosity"))
        parser = optparse.OptionParser(option_list=option_list)
        options, args = parser.parse_args()
        if options.gui or (len(sys.argv) < 2):
            if not HAS_GUI:
                print "System does not support the GUI component."
                parser.print_help()
                sys.exit(1)
            reader = SymbolUI()
            gtk.main()
        else:
            reader = SEEDReader()
            reader.verbosity         = options.verbosity
            for arg in args:
                reader.add_files(glob.glob(arg))
            thread = ReadThread()
            thread.set_reader(reader)
            thread.start()
            while thread.isAlive() or reader.is_running() or reader.log_queue.qsize():
                try:
                    sys.stdout.write(reader.log_queue.get(False, 0.2))
                except Queue.Empty:
                    pass
    except KeyboardInterrupt:
        if reader and reader.is_running():
            thread.halt()
            thread.join()
        print "Keyboard Interrupt [^C]"

# /*}}}*/

if __name__ == "__main__":
    main()

