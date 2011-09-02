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


# === SEEDReader Class /*{{{*/
class SEEDReader:
    def __init__(self):
        self.files = []
        self.verbosity = 0
        self.succinct = False
        self.print_unknowns = False
        self.circular = False
        self.num_records = 0
        self.reading = False
        self.report_file_names = False
        self.log_queue = Queue.Queue()
        self.start_callback = None
        self.finish_callback = None

    def stop(self):
        self.reading = False

    def run(self):
        self.reading = True
        if self.start_callback:
            self.start_callback()
        self._run()
        if self.finish_callback:
            self.finish_callback()
        self.reading = False

    def _run(self):
        for file in self.files:
            if not self.reading:
                self._log('File processing canceled.\n')
                break
            self._process_file(file)
        if not self.succinct:
            self._log('Done.\n')

    def is_running(self):
        return self.reading

    def _log(self, log_str):
        self.log_queue.put_nowait(log_str)

    def clear_files(self):
        self.files = []

    def add_file(self, file):
        if not self.is_running():
            self.files.append(file)

    def add_files(self, files):
        if not self.is_running():
            self.files.extend(files)

    def set_start_callback(self, callback):
        if not callable(callback):
            raise TypeError("SEEDReader::set_start_callback(callback): argument must be callable")
        self.finish_callback = callback

    def set_finish_callback(self, callback):
        if not callable(callback):
            raise TypeError("SEEDReader::set_finish_callback(callback): argument must be callable")
        self.finish_callback = callback


    def _cal_type_string(self, type, extn=True):
        if type == 300:
            if extn: return "Step cal.   "
            else:   return "Step"
        elif type == 310:
            if extn: return "Sine cal.   "
            else:   return "Sine"
        elif type == 320:
            if extn: return "Random cal. "
            else:   return "Random"
        elif type == 390:
            if extn: return "Generic cal."
            else:   return "Generic"

    def _time_compare(self, a, b):
        for i in range(0, 7):
            if a[i] != b[i]:
                return a[i] - b[i]
        return 0

    def _process_file(self, file_name):
        circular = self.circular
        if (not os.path.exists(file_name)) or (not os.path.isfile(file_name)):
            self._log("Unable to locate file '%s'\n" % file_name)
            return

        if circular:
            if file_name[-4:] != '.buf':
                self._log("File '%s' does not appear to be a circular buffer.\n" % file_name)
                return
            if not os.path.isfile(file_name[:-4] + '.idx'):
                self._log("File '%s' does not have an accompanying .idx file.\n" % file_name)
                return

        file_stats = os.stat(file_name)

        if file_stats[stat.ST_SIZE] < 256:
            self._log("File '%s' is too small to contain SEED data.\n" % file_name)
            return

        fh = open(file_name, 'rb')
        record = fh.read(256)
        index = struct.unpack('>H', record[46:48])[0]
        if index >= len(record) - 48:
            self._log("File '%s' is not valid SEED. Index of first blockette is out of range.\n" % file_name)
            return
        blockette_type = struct.unpack('>H', record[index:index+2])[0]
        if blockette_type != 1000:
            self._log("File '%s' is not valid SEED. First blockette of a SEED record should always be type 1000.\n" % file_name)
            return

        record_length = 2 ** struct.unpack('>B', record[index+6:index+7])[0]
        if record_length < 256:
            self._log("File '%s' is not valid SEED. Recod length must be 256 bytes or greater.\n" % file_name)
            return

        if self.report_file_names:
            self._log("Processing file %s\n" % file_name)

        total_records = file_stats[stat.ST_SIZE] / record_length
        total_file_bytes = record_length * total_records
        st_name, ch_loc, ch_name, st_net = struct.unpack('>5s2s3s2s', record[8:20])

        num_records = self.num_records

        if not num_records:
            num_records = total_records
        elif num_records > total_records:
            num_records = total_records

        idx_last = 0
        idx_max  = 0
        if circular:
            index_file = file_name[:-4] + '.idx'
            ifh   = open(index_file, 'r')
            lines = ifh.readlines()
            ifh.close()
            if (type(lines) != list) or (len(lines) != 3):
                self._log("'%s' file does not contain three lines.\n" % index_file)
                return
            if not ((lines[0] == lines[1]) and (lines[0] == lines[2])):
                self._log("'%s' lines do not match.\n" % index_file)
                return
            try:
                idx_last,idx_max = tuple(map(int, lines[0].strip().split(' ', 1)))
            except ValueError:
                self._log("'%s' lines are invalid.\n" % index_file)
            if not idx_max:
                self._log("'%s' states circular buffer max size is 0.\n" % index_file)
                return
            if idx_last > idx_max:
                self._log("'%s' last index greater than max size.\n" % index_file)
                return
            if idx_last > total_records:
                self._log("'%s' last index greater than buffer file size.\n" % index_file)
                return
            # If the circular buffer isn't full, we can treat it like a flat file
            if idx_max > total_records:
                circular = False

        if not self.succinct:
            self._log("===============================================================\n")
            self._log("\n")
        if (self.verbosity > 0) and (not self.succinct):
            self._log("RECORD SIZE --- %d bytes\n" % record_length)
            self._log("RECORD COUNT -- %d\n" % total_records)
            self._log("TOTAL SIZE ---- %d bytes\n\n" % file_stats[stat.ST_SIZE])

        seek_pos = 0
        if circular:
            seek_pos = idx_last * record_length
            fh.seek(seek_pos,0)
            record = fh.read(record_length)
            if len(record) != record_length:
                self._log("Circular buffer pre-processing failed (mis-calculated file size, whoops).\n")
            if total_file_bytes <= fh.tell():
                fh.seek(0,0)
            timestamp = tuple(struct.unpack('>HHBBBBH', record[20:30]))
            record_count = 1
            while 1:
                if not self.reading: return

                # Give us a little cheat room
                if record_count >= (total_records + 2):
                    break
                record = fh.read(record_length)
                if len(record) != record_length:
                    self._log("Circular buffer pre-processing failed (mis-calculated file size, whoops).\n")
                if total_file_bytes <= fh.tell():
                    fh.seek(0,0)
                old_timestamp = timestamp
                record_count += 1
                timestamp = tuple(struct.unpack('>HHBBBBH', record[20:30]))
                if self._time_compare(old_timestamp, timestamp) < 0:
                    index = fh.tell()
                    if index <= record_length:
                        seek_pos = (total_records - 1) * total_records
                    else:
                        seek_pos = index - record_length
                    break
            if (not self.succinct) and (self.verbosity > 0):
                self._log("Scanned %d records looking for first in circular buffer\n" % record_count)
        else:
            if num_records < total_records:
                seek_pos = (total_records - num_records) * record_length
        fh.seek(seek_pos, 0)

        record_count = 0
        while 1:
            if not self.reading: return

            if record_count >= num_records:
                if not self.succinct:
                    self._log("Done reading file.\n")
                break

            if circular:
                if fh.tell() >= (record_length * total_records):
                    fh.seek(0,0)

            record = fh.read(record_length)
            if len(record) != record_length:
                if not self.succinct:
                    self._log("Done reading file (mis-calculated file size, whoops).\n")
                break
            record_count += 1

            st_name, ch_loc, ch_name, st_net = struct.unpack('>5s2s3s2s', record[8:20])

            if self.verbosity > 4:
                position = fh.tell()
                year,jday,hour,min,sec,_,tmsec = tuple(struct.unpack('>HHBBBBH', record[20:30]))
                self._log("Record %d [%d:%d] {%d:%d} " % (record_count,(position-record_length)/record_length,position/record_length,position-record_length,position))
                self._log("[%04u,%03u %02u:%02u:%02u.%04u]\n" % (year, jday, hour, min, sec, tmsec))
            elif self.verbosity > 3:
                position = fh.tell()
                self._log("Record %d [%d:%d] {%d:%d}\n" % (record_count,(position-record_length)/record_length,position/record_length,position-record_length,position))

            next_blockette = struct.unpack('>H', record[46:48])[0]
            while next_blockette != 0:
                # Check for cancel message
                if not self.reading: return

                index = next_blockette
                blockette_type, next_blockette = struct.unpack('>HH', record[index:index+4])
                if blockette_type in (300, 310, 320, 390):
                    year,jday,hour,min,sec,_,tmsec,_,cal_flags,duration = tuple(struct.unpack('>HHBBBBHBBL', record[index+4:index+20]))
                    if self.succinct:
                        if cal_flags & 0x8:
                            self._log("  ")
                        self._log("[%s_%s %s-%s]> %s [%04u,%03u %02u:%02u:%02u.%04u] %lu seconds\n" % (st_net, st_name, ch_loc, ch_name, self._cal_type_string(blockette_type), year, jday, hour, min, sec, tmsec, duration/10000))
                    else:
                        self._log("Found a %s Calibration Blockette\n" % self._cal_type_string(blockette_type, False))
                        self._log("  Starting Time:  %04u,%03u %02u:%02u:%02u.%04u\n" % (year, jday, hour, min, sec, tmsec))
                        if self.verbosity > 0:
                            self._log("  Blockette Type: %lu\n" % blockette_type)
                            self._log("  Next Blockette: %lu\n" % next_blockette)
                        self._log("  Calibration Duration: %lu seconds\n" % (duration / 10000,))
                        if duration % 10000:
                            self._log(" + %lu tenth-milliseconds" % (duration % 10000,))
                    if blockette_type == 300:
                        step_count,_,_,ntrvl_duration,amplitude,cal_input = struct.unpack('>BBLLf3s', record[index+14:index+31])
                        if not self.succinct:
                            self._log("  Interval Duration: %lu seconds\n" % (ntrvl_duration / 10000,))
                            self._log("  Number of Steps: %lu\n" % step_count)

                            self._log("  Amplitude: %f\n" % amplitude)
                            self._log("  Input Channel: %s\n" % cal_input)
                            self._log("  Flags: %02x\n" % cal_flags)
                            if cal_flags & 0x01:
                                self._log("    Sign: Positive\n")
                            else:
                                self._log("    Sign: Negative\n")
                            if cal_flags & 0x02:
                                self._log("    Coupling: Capacitive\n")
                            else:
                                self._log("    Coupling: Resistive\n")
                            if cal_flags & 0x04:
                                self._log("    Autocal: Yes\n")
                            else:
                                self._log("    Autocal: No\n")
                            if cal_flags & 0x08:
                                self._log("    Continuation: Yes\n")
                            else:
                                self._log("    Continuation: No\n")

                    if blockette_type == 310:
                        signal_period,amplitude,cal_input = struct.unpack('>ff3s', record[index+20:index+31])

                        if not self.succinct:
                            self._log("  Frequency: %.3f Hz\n" % (1.0/signal_period,))
                            self._log("  Amplitude: %f\n" % amplitude)
                            self._log("  Input Channel: %s\n" % cal_input)
                            self._log("  Flags: %02x\n" % cal_flags)
                            if cal_flags & 0x04:
                                self._log("    Autocal: Yes\n")
                            else:
                                self._log("    Autocal: No\n")
                            if cal_flags & 0x08:
                                self._log("    Continuation: Yes\n")
                            else:
                                self._log("    Continuation: No\n")
                            if cal_flags & 0x10:
                                self._log("    Amplitude Measurement: Peak-to-Peak\n")
                            elif cal_flags & 0x20:
                                self._log("    Amplitude Measurement: Zero-to-Peak\n")
                            elif cal_flags & 0x40:
                                self._log("    Amplitude Measurement: RMS\n")
                            else:
                                self._log("    Amplitude Measurement: Uspecified\n")
                    if blockette_type == 320:
                        amplitude,cal_input = struct.unpack('>f3s', record[index+20:index+27])
                        if not self.succinct:
                            self._log("  Amplitude: %f\n" % amplitude)
                            self._log("  Input Channel: %s\n" % cal_input)
                            self._log("  Flags: %02x\n" % cal_flags)
                            if cal_flags & 0x04:
                                self._log("    Autocal: Yes\n")
                            else:
                                self._log("    Autocal: No\n")
                            if cal_flags & 0x08:
                                self._log("    Continuation: Yes\n")
                            else:
                                self._log("    Continuation: No\n")
                            if cal_flags & 0x10:
                                self._log("    Random Amplitudes: Yes\n")
                            else:
                                self._log("    Random Amplitudes: No\n")
                    if blockette_type == 390:
                        amplitude,cal_input = struct.unpack('>f3s', record[index+20:index+27])
                        if not self.succinct:
                            self._log("  Amplitude: %f\n" % amplitude)
                            self._log("  Input Channel: %s\n" % cal_input)
                            self._log("  Flags: %02x\n" % cal_flags)
                            if cal_flags & 0x04:
                                self._log("    Autocal: Yes\n")
                            else:
                                self._log("    Autocal: No\n")
                            if cal_flags & 0x08:
                                self._log("    Continuation: Yes\n")
                            else:
                                self._log("    Continuation: No\n")
                elif blockette_type == 395:
                    year,jday,hour,min,sec,_,tmsec = tuple(struct.unpack('>HHBBBBH', record[index+4:index+14]))
                    if self.succinct:
                        self._log("[%s_%s %s-%s]> Cal. Abort   [%04u,%03u %02u:%02u:%02u.%04u]\n" % (st_net, st_name, ch_loc, ch_name, year, jday, hour, min, sec, tmsec))
                    else:
                        self._log("Found a Calibration Abort Blockette\n")
                        self._log("  Stop Time:  %04u,%03u %02u:%02u:%02u.%04u\n" % (year, jday, hour, min, sec, tmsec))
                else:
                    if self.print_unknowns:
                        self._log("Skipping non-calibration blockette [type %d]\n" % blockette_type)
                    continue

                # Cycle back around if we have reached the end of the file
                if circular and (total_file_bytes <= fh.tell()):
                    fh.seek(0,0)
        
        if not self.succinct:
            self._log("Number of %d-byte SEED records: %d\n\n" % (record_length, record_count))
        fh.close()
#/*}}}*/

# === ReadThread Class /*{{{*/
class ReadThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True
        self.reader = None

    def set_reader(self, reader):
        self.reader = reader

    def halt(self):
        self.reader.stop()

    def run(self):
        try:
            if not self.reader:
                raise ValueError("reader not supplied")
            elif not hasattr(self.reader, 'run') or not callable(self.reader.run):
                raise TypeError("supplied reader is has no run() method")
            self.reader.run()
        except KeyboardInterrupt:
            pass
        except:
            pass
#/*}}}*/

# === WriteThread Class /*{{{*/
class WriteThread(threading.Thread):
    def __init__(self, gui):
        threading.Thread.__init__(self)
        self.daemon = True
        self.writing = False
        self.write_to_stdout = False
        self.log_queue = None
        self.text_buffer = None
        self.clear_request_queue = Queue.Queue()
        self.callback_poll = None
        self.gui = gui

    def set_queue(self, log_queue):
        if not log_queue: 
            raise ValueError("WriteThread::set_queue(log_queue): argument is None")
        if not hasattr(log_queue, '__class__'):
            raise TypeError("WriteThread::set_queue(log_queue): argument is not a class")
        if not hasattr(log_queue.__class__, '__name__'):
            raise TypeError("WriteThread::set_queue(log_queue): argument class has no __name__ attribute")
        if log_queue.__class__.__name__ != 'Queue':
            raise TypeError("WriteThread::set_queue(log_queue): argument class is not a Queue")
        self.log_queue = log_queue

    # Run this operation on every iteration (poll)
    def set_poll(self, callback):
        if not callable(callback):
            raise TypeError("WriteThread::set_poll(callback): argument must be callable")
        self.callback_poll = callback

    def to_stdout(self, to_stdout):
        if type(to_stdout) != bool:
            raise TypeError("WriteThread::to_stdout(to_stdout): argument must be type boolean")
        self.write_to_stdout = to_stdout

    def halt(self):
        self.writing = False

    def clear(self):
        try:
            self.clear_request_queue.put_nowait('clear')
        except:
            pass

    def run(self):
        try:
            self.writing = True
            while self.writing:
                if self.callback_poll:
                    self.callback_poll()
                try:
                    content = self.log_queue.get(True, 0.1)
                    self.gui.log_queue.put(content)
                    gobject.idle_add(gobject.GObject.emit, self.gui.hbutton_log_to_display, 'clicked')
                    if self.write_to_stdout:
                        sys.stdout.write(content)
                        sys.stdout.flush()
                except Queue.Empty:
                    pass
        except KeyboardInterrupt:
            pass
        except:
            pass

#/*}}}*/
        
# === CalsUI Class (GTK+ Graphical Interface) /*{{{*/
class CalsUI:
    def __init__(self):
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title("Calibrations")
        self.window.set_icon(asl.new_icon('caldump'))

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
        self.hbutton_log_to_display = gtk.Button()
        self.hbutton_log_to_display.connect('clicked', self.callback_log_to_display, None)

        self.files  = []
        self.log_queue = Queue.Queue()
        self.reader = SEEDReader()
        self.reader.set_start_callback(self.update_interface)
        self.reader.set_finish_callback(self.update_interface)
        
        self.thread_writer = WriteThread(self)
        self.thread_writer.set_queue(self.reader.log_queue)
        self.thread_writer.to_stdout(False)
        self.thread_writer.set_poll(self.update_interface)
        self.thread_writer.start()

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

    def callback_log_to_display(self, widget, event, data=None):
        try:
            while 1:
                message = self.log_queue.get_nowait()
                self.textbuffer_display.insert_at_cursor(message)
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
        option_list.append(optparse.make_option("-c", "--circular-buffer", dest="circular", action="store_true", help="files should be treated as circular buffers with matching idx file"))
        option_list.append(optparse.make_option("-g", "--gui", dest="gui", action="store_true", help="launch in graphical mode"))
        option_list.append(optparse.make_option("-n", "--number-of-records", dest="numrecs", type="int", action="store", help="maximum number of SEED records to read"))
        option_list.append(optparse.make_option("-r", "--report-file-names", action="store_true", dest="report_file_names", help="report the name of each valid file"))
        option_list.append(optparse.make_option("-s", "--succinct", action="store_true", dest="succinct", help="print one line per blockette"))
        option_list.append(optparse.make_option("-u", "--print-unknowns", action="store_true", dest="unknowns", help="print types of found non-calibration blockettes"))
        option_list.append(optparse.make_option("-v", action="count", dest="verbosity", help="specify multiple time to increase verbosity"))
        parser = optparse.OptionParser(option_list=option_list)
        options, args = parser.parse_args()
        if options.gui or (len(sys.argv) < 2):
            if not HAS_GUI:
                print "System does not support the GUI component."
                parser.print_help()
                sys.exit(1)
            reader = CalsUI()
            gtk.main()
        else:
            reader = SEEDReader()
            reader.succinct          = options.succinct
            reader.verbosity         = options.verbosity
            reader.print_unknowns    = options.unknowns
            reader.circular          = options.circular
            reader.num_records       = options.numrecs
            reader.report_file_names = options.report_file_names
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

