#!/usr/bin/env python
import asl

import calendar
import glob
import optparse
import os
import Queue
import re
import shutil
import stat
import struct
import sys
import threading
import time
import traceback

# === GUI Modules and Initialization /*{{{*/
try:
    try: import pygtk
    except: 
        message = ("PyGTK Not Found", "PyGTK could not be found on your system")
        raise
    try: pygtk.require('2.0')
    except: 
        message = ("PyGTK Version Error", "Wrong version of PyGTK (2.0+ required)")
        raise
    try:
        import gtk
        import gobject
        import pango
        gobject.threads_init()
    except Exception, e:
        message = ("PyGTK Error", "Error setting up PyGTK.\nException: %s" % str(e))
        raise
except:
    try: 
        import tkMessageBox
        tkMessageBox.showerror(*message)
    except:
        print message[1]
        sys.exit(1)

try: import gio
except:
    try: import gnomevfs
    except:
        message = gtk.MessageDialog(parent=None, type=gtk.MESSAGE_ERROR, buttons=gtk.BUTTONS_OK)
        message.set_markup("Your system does not support Gio or GnomeVFS.\nFile Manager needs at least one of these modules.")
        message.run()
        message.destroy()
        sys.exit(1)
#/*}}}*/

from jtk.Thread import Thread
from jtk.Logger import LogThread
from jtk.StatefulClass import StatefulClass

# === Definitions/*{{{*/
COLUMN_HIDE = False
COLUMN_SHOW = True

DND_URI_TUPLE = ("text/uri-list", 0, 25)
#DND_FILESOURCE_TUPLE = ("pitivi/file-source", 0, 26)

FILE_OP_UNKNOWN   = 0
FILE_OP_DELETE    = 1
FILE_OP_COPY      = 2
FILE_OP_MOVE      = 3
FILE_OP_LINK      = 4
FILE_OP_MKDIR     = 5
FILE_OP_SPEEDWALK = 6

FILE_ERR_DNE  = -1
FILE_ERR_PERM = -2

POLICY_CHECK     = 0
POLICY_SKIP      = 1
POLICY_IGNORE    = 2
POLICY_OVERWRITE = 3
#/*}}}*/

# === FileWalker Class/*{{{*/
class FileWalker(Thread):
    def __init__(self, action, sources, destination='', output_queue=None, update_callback=None, completion_callback=None):
        Thread.__init__(self)
        self.count = 0

        self.action = action
        self.sources = sources
        self.destination = destination
        self.output_queue = output_queue
        self.update_callback = update_callback
        self.completion_callback = completion_callback

    def queue_file(self, message, file):
        if self.output_queue:
            self.output_queue.put((message,file))

    def increment_count(self):
        self.count += 1
        if self.update_callback:
            self.update_callback()

    def walk_dir(self, src_dir, dst_dir):
        self.increment_count()
        self.queue_file(FILE_OP_MKDIR, dst_dir)
        for file in os.listdir(src_dir):
            if not self.running:
                return
            src_path = os.path.abspath(src_dir + '/' + file)
            dst_path = os.path.abspath(dst_dir + '/' + file)
            if os.path.isdir(src_path):
                self.walk_dir(src_path, dst_path)
            elif os.path.isfile(src_path):
                self.queue_file(self.action, (src_path,dst_path))
                self.increment_count()

    def walk_dir_delete(self, dir):
        self.increment_count()
        for file in os.listdir(dir):
            if not self.running:
                return
            path = os.path.abspath(dir + '/' + file)
            if os.path.isdir(path):
                self.walk_dir_delete(path)
            elif os.path.isfile(path):
                self.queue_file(self.action, path)
                self.increment_count()
        self.queue_file(FILE_OP_RMDIR, dir)

    def walk_dir_fast(self, dir):
        self.increment_count()
        for file in os.listdir(dir):
            if not self.running:
                return
            path = os.path.abspath(dir + '/' + file)
            if os.path.isdir(path):
                self.walk_dir_fast(path)
            elif os.path.isfile(path):
                self.increment_count()

    def halt_now(self):
        self.running = False

    def run(self):
        if self.action in (FILE_OP_COPY, FILE_OP_MOVE):
            if not self.destination:
                print "No destination provided for copy or move."
                self.queue_file('DONE', None)
                return
        self.running = True
        for file in self.sources:
            print "Walking"
            if not self.running:
                break
            if not os.path.exists(file):
                continue
            elif os.path.isdir(file):
                if self.action == FILE_OP_SPEEDWALK:
                    self.walk_dir_fast(file)
                elif self.action == FILE_OP_DELETE:
                    self.walk_dir_delete(file)
                elif self.action in (FILE_OP_COPY, FILE_OP_MOVE):
                    dst = os.path.abspath(self.destination + '/' + file.split()[-1])
                    self.walk_dir(file,dst)
            elif os.path.isfile(file):
                if self.action == FILE_OP_DELETE:
                    self.queue_file(self.action,file)
                elif self.action in (FILE_OP_COPY, FILE_OP_MOVE):
                    dst = os.path.abspath(self.destination + '/' + file.split()[-1])
                    self.queue_file(self.action,(file,dst))
                self.increment_count()
            else:
                print "Skipping non-regular file '%s'" % file
        print "Tired."
        self.queue_file('DONE', None)
        self.running = False
        if self.completion_callback:
            self.completion_callback()
#/*}}}*/

# === FileOperation Class/*{{{*/
class FileOperation(Thread):
    def __init__(self, action, files, destination='', context=None, completion_callback=None, completion_data=None, prescan=True):
        Thread.__init__(self, queue_max=8192)
        self.progress_queue = Queue.Queue()
        self.handlers = []

        self.completion_callback = completion_callback
        self.completion_data = completion_data

        self.window = gtk.Window()
        self.window.set_title("File Operation")
        self.window.set_icon(asl.new_icon('file_manager'))

        self.hbox = gtk.HBox()
        self.progress = gtk.ProgressBar()
        self.progress.set_pulse_step(0.01)
        self.button_cancel = gtk.Button(stock=gtk.STOCK_CANCEL)

        self.window.add(self.hbox)
        self.hbox.pack_start(self.progress,      False, True,  2)
        self.hbox.pack_start(self.button_cancel, False, False, 2)

        id = self.button_cancel.connect("clicked", self.callback_cancel, None)
        self.handlers.append((id, self.button_cancel))

        self.hbutton_progress_pulse = gtk.Button()
        id = self.hbutton_progress_pulse.connect("clicked", self.callback_pulse_progress, None)
        self.handlers.append((id, self.hbutton_progress_pulse))

        self.hbutton_progress_update = gtk.Button()
        id = self.hbutton_progress_update.connect("clicked", self.callback_update_progress, None)
        self.handlers.append((id, self.hbutton_progress_update))

        id = None

        self.window.show_all()

        self.context     = context
        self.action      = action
        self.files       = files
        self.destination = destination

        self.policy_same_file   = None
        self.policy_file_exists = None
        self.policy_permission  = None

        self.walker_thread = None
        self.scan_lock = threading.Lock()
        self.prescan_lock = threading.Lock()
        self.prescan_lock.acquire()

        if not prescan:
            self.prescan_lock.release()
            self.prescan_walker = None
        else:
            print "pre-scanning"
            self.progress.set_text("Pre-Scan...")
            self.prescan_walker = FileWalker(FILE_OP_SPEEDWALK, self.files, update_callback=self.pulse_progress, completion_callback=self.callback_prescan_complete)
            self.prescan_walker.start()

    def __del__(self):
        self.window.hide()
        for id,widget in self.handlers:
            widget.disconnect(id)
        del self.window

    def get_context(self):
        return self.context

    def set_context(self, context):
        self.context = context

    def callback_cancel(self, widget, event, data=None):
        if not self.prescan_lock.acquire(0):
            if self.prescan_walker:
                self.prescan_walker.halt_now()
        else:
            self.prescan_lock.release()
        if not self.scan_lock.acquire(0):
            if self.walker_thread:
                self.walker_thread.halt_now()
        else:
            self.scan_lock.release()
        self.halt_now()

    def callback_update_progress(self, widget, event, data=None):
        try:
            progress,total = self.progress_queue.get()
            try: self.progress_queue.task_done()
            except: pass
            self.progress.set_text("processing file %d of %d" % (progress,total))
            self.progress.set_fraction(float(progress)/float(total))
        except Queue.Empty:
            pass

    def callback_pulse_progress(self, widget, event, data=None):
        self.progress.pulse()

    def callback_prescan_complete(self):
        self.total = self.prescan_walker.count
        self.count = 0
        del self.prescan_walker
        self.prescan_lock.release()

    def update_progress(self, progress, total):
        self.progress_queue.put((progress,total))
        gobject.idle_add(gobject.GObject.emit, self.hbutton_progress_update, 'clicked')

    def pulse_progress(self):
        gobject.idle_add(gobject.GObject.emit, self.hbutton_progress_pulse, 'clicked')

    def _pre(self):
        print "waiting on lock"
        self.prescan_lock.acquire()
        self.prescan_lock.release()
        self.scan_lock.acquire()
        self.walker_thread = FileWalker(self.action, self.files, self.destination, self.queue)
        self.walker_thread.start()

    def _run(self, message, data):
        self.count += 1
        #time.sleep(0.1)
        self.update_progress(self.count, self.total)
        return #TODO: comment out and test

        if message == FILE_OP_DELETE:
            try: #os.remove(data)
                print "Removing file %s" % data
            except: print "Insufficient permissions to remove the file."
        elif message in FILE_OP_COPY:
            src,dst = data
            try: #shutil.copy(src,dst)
                print "Copying %s to %s" % (src, dst)
            except Error:
                print "Source and destination are the same file."
            except IOError:
                print "Insufficient permissions to create the destination file."
        elif message == FILE_OP_MOVE:
            src,dst = data
            try: #os.rename(src,dst)
                print "Renaming %s to %s" % (src, dst)
            except OSError:
                print "File exists, attempting overwrite"
                try: #shutil.copy(src,dst)
                    print "Overwriting file %s" % dst
                except Error: print "Source and destination are the same file."
                except IOError: print "Insufficient permissions to create the destination file." 
                try: #os.remove(src)
                    print "Removing source file" % src
                except: print "Insufficient permissions to remove the source file." 
        elif message == FILE_OP_LINK:
            src,dst = data
            try: #os.symlink(src,dst)
                print "Creating symlink to %s as %s" % (src, dst)
            except: print "Unable to create symblic link."
        elif message == FILE_OP_MKDIR:
            try: #os.mkdir(data)
                print "Creating directory %s" % data
            except OSError: print "Directory already exists or insufficient permissions."
        elif message == FILE_OP_RMDIR:
            try: #os.rmdir(data)
                print "Removing directory %s" % data
            except OSError: print "Insufficient permissions to remove the directory."
        self.update_progress(self.count, self.total)

    def _post(self):
        self.window.hide()
        if self.completion_callback:
            self.completion_callback(self.completion_data)
#/*}}}*/

# === PathWidget Class/*{{{*/
class PathWidget(gtk.HBox):
    def __init__(self, callback):
        gtk.HBox.__init__(self)
        self._path = os.path.abspath('.')
        self._buttons = []
        self._update_callback = callback
        self._lock_update = threading.Lock()

        self.update()

    def step_in(self, file):
        dest = os.path.abspath(self._path + '/' + file)
        if os.path.isdir(dest):
            self._path = dest
            self.update()

    def step_out(self, real=False):
        path = self._path
        if real:
            path = os.path.realpath(self._path)
        dest = os.path.abspath(os.path.split(path)[0])
        if dest == '':
            return
        if os.path.isdir(dest):
            self._path = dest
            self.update()

    def set_path(self, path):
        try:
            self._path = os.path.abspath(path)
            if not os.path.exists(self._path):
                return
        except:
            return
        self.update()

    def get_path(self):
        return self._path

    def update(self):
        if not self._lock_update.acquire(0):
            return
        dirs = []
        path = self._path
        while 1:
            path,dir = os.path.split(path)
            dirs.insert(0, dir)
            if dir == '':
                break
        idx = 0
        max = len(dirs)
        b_count = len(self._buttons)
        modified = False
        path = ''
        while idx < max:
            dir = dirs[idx]
            path = os.path.abspath(path + '/' + dir)
            if idx >= b_count:
                button = gtk.Button(dir)
                button.connect('clicked', self.callback_jump, None, idx)
                button._path = path
                button._dir  = dir
                self.pack_start(button, False, False, 2)
                self._buttons.append(button)
            else:
                button = self._buttons[idx]

            if dir != button._dir:
                modified = True
                button._path = path
                button._dir  = dir
                button.set_label(dir)
            if idx == (max-1):
                button.modify_font(pango.FontDescription('bold'))
            else:
                button.modify_font(pango.FontDescription('normal'))
            idx += 1

        while idx < b_count:
            if modified:
                button = self._buttons.pop(-1)
                self.remove(button)
                del button
            else:
                self._buttons[idx].modify_font(pango.FontDescription('normal'))
            idx += 1

        self.show_all()

        self._lock_update.release()

    def callback_jump(self, widget, event, index=None):
        self.set_path(self._buttons[index]._path)
        self._update_callback()
#/*}}}*/

# === FileWidget Class/*{{{*/
class FileWidget(gtk.VBox):
    def __init__(self):
        gtk.VBox.__init__(self)

        #self._root = os.path.abspath('/data/temp_data')

        self._column_defs = [
            ('icon',    '',             gtk.gdk.Pixbuf,      'pixbuf',  COLUMN_SHOW),
            ('name',    'Name',         gobject.TYPE_STRING, 'text',    COLUMN_SHOW),
            ('type',    'Type',         gobject.TYPE_STRING, 'text',    COLUMN_SHOW),
            ('perm',    'Permissions',  gobject.TYPE_STRING, 'text',    COLUMN_SHOW),
            ('mode',    'Mode',         gobject.TYPE_LONG,   'text',    COLUMN_HIDE),
            ('ino',     'Inode',        gobject.TYPE_LONG,   'text',    COLUMN_HIDE),
            ('dev',     'Device',       gobject.TYPE_LONG,   'text',    COLUMN_HIDE),
            ('nlink',   'Link Count',   gobject.TYPE_LONG,   'text',    COLUMN_HIDE),
            ('uid',     'User',         gobject.TYPE_LONG,   'text',    COLUMN_HIDE),
            ('gid',     'Group',        gobject.TYPE_LONG,   'text',    COLUMN_HIDE),
            ('size',    'Size',         gobject.TYPE_INT64,  'text',    COLUMN_SHOW),
            ('atime',   'Accessed',     gobject.TYPE_LONG,   'text',    COLUMN_HIDE),
            ('mtime',   'Modified',     gobject.TYPE_LONG,   'text',    COLUMN_HIDE),
            ('ctime',   'Created',      gobject.TYPE_LONG,   'text',    COLUMN_HIDE),
        ]

        self._icons = {}
        self._icon_width = 32
        self._icon_height = 32
        self._columns = {}
        self._sort_order = gtk.SORT_ASCENDING
        self._folders_first = True
        self._file_operations = {}
        self._max_id = 0
        self._main_window_closed = False

        self._lock_shutdown = threading.Lock()
        self._lock_fileop   = threading.Lock()
        self._lock_path     = threading.Lock()

# ===== GUI Build-up ========================================
        args = map(lambda c: c[2], self._column_defs)
        self.treestore = gtk.TreeStore(*args)

        try:
            self.tooltips = gtk.Tooltips()
        except:
            self.tooltips = None

# ===== Widget Creation ============================================
        self.scroll_treeview    = gtk.ScrolledWindow()
        self.scroll_iconview    = gtk.ScrolledWindow()

        self.treeview           = gtk.TreeView(self.treestore)
        self.iconview           = gtk.IconView()

        self.scroll_iconview.add(self.iconview)
        self.scroll_treeview.add(self.treeview)

        idx = 0
        model = self.treestore
        for id,title,type,attribute,show in self._column_defs:
            tvc = gtk.TreeViewColumn(title)
            if attribute == 'pixbuf':
                cr = gtk.CellRendererPixbuf()
            else:
                cr = gtk.CellRendererText()
            tvc.pack_start(cr, True)
            tvc.add_attribute(cr, attribute, idx)
            tvc.set_cell_data_func(cr, self.cdf_format_files, (id,attribute))

            column = {}
            self._columns[id] = column
            column['index']          = idx
            column['treeviewcol']    = tvc
            column['cellrenderer']   = cr
            column['show']           = show
            column['regex']          = None

            if show:
                self.treeview.append_column(tvc)
            model.set_sort_func(idx, self.sort_files, id)
            idx += 1

        self.path = PathWidget(self.callback_path_updated)

        self.pack_start(self.path,              False, True,  2)
        self.pack_start(self.scroll_treeview,   True,  True,  2)

        self.treeview.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.scroll_iconview.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scroll_treeview.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        #self.treeview.drag_data_received = self.drag_data_received

        self.path.set_path('.')

        self.connect("key-press-event", self.callback_key_pressed, None)
        #self.connect("key-release-event", self.callback_key_released, None)

        self.treeview.drag_dest_set(gtk.DEST_DEFAULT_DROP | gtk.DEST_DEFAULT_MOTION, [DND_URI_TUPLE], gtk.gdk.ACTION_COPY)
        self.treeview.drag_source_set(gtk.gdk.BUTTON1_MASK, [DND_URI_TUPLE], gtk.gdk.ACTION_COPY)
        self.treeview.connect("row-activated",      self.callback_row_activated, None)
        self.treeview.connect("drag-begin",         self.callback_dnd_begin,     None)
        self.treeview.connect("drag-data-delete",   self.callback_dnd_delete,    None)
        self.treeview.connect("drag-data-get",      self.callback_dnd_get,       None)
        self.treeview.connect("drag-data-received", self.callback_dnd_received,  None)
        self.treeview.connect("drag-drop",          self.callback_dnd_drop,      None)
        #self.treeview.connect("drag-end",           self.callback_dnd_end,       None)
        #self.treeview.connect("drag-failed",        self.callback_dnd_failed,    None)
        self.treeview.connect("drag-motion",        self.callback_dnd_motion,    None)

        self.show_all()
        self.update()

    def cdf_format_files(self, column, cell, model, iter, data=None):
        id,attr = data
        if attr == 'text':
            cell.set_property("foreground", "#000000")

# ===== Callback Methods =============================================
    def callback_dnd_begin(self, widget, drag_context, params=None):
        selection = self.treeview.get_selection()
        if not selection:
            selection_count = 0
        else:
            selection_count = len(selection.get_selected_rows())
        if selection_count < 1:
            context.drag_abort(int(time.time()))
        else:
            if selection_count == 1:
                self.treeview.drag_source_set_icon_stock(gtk.STOCK_DND)
            else:
                self.treeview.drag_source_set_icon_stock(gtk.STOCK_DND_MULTIPLE)

    def callback_dnd_delete(self, widget, drag_context, params=None):
        # Delete source data
        pass

    def callback_dnd_get(self, widget, drag_context, selection_data, info, timestamp, params=None):
        # Send data to the destination
        uris = []
        refs = self.get_selected_files()
        model = self.treestore
        directory = self.path.get_path()
        index = self._columns['name']['index']
        for ref in refs:
            path = ref.get_path()
            iter = model.get_iter(path)
            name = model.get_value(iter, index)
            uris.append(os.path.abspath(directory + '/' + name))
        if info == DND_URI_TUPLE[-1]:
            selection_data.set(selection_data.target, 8, '\n'.join(uris))

    def callback_dnd_received(self, widget, drag_context, x, y, selection_data, info, timestamp, params=None):
        # Got data from source, insert, and possibly request delete
        if info == DND_URI_TUPLE[-1]:
            try:
                uris = map(lambda s: s.strip(), selection_data.data.split('\n'))
                action = FILE_OP_UNKNOWN
                if drag_context.action == gtk.gdk.ACTION_COPY:
                    action = FILE_OP_COPY
                elif drag_context.action == gtk.gdk.ACTION_MOVE:
                    action = FILE_OP_MOVE
                elif drag_context.action == gtk.gdk.ACTION_LINK:
                    action = FILE_OP_LINK
                fileop = FileOperation(action, uris, self.path.get_path(), drag_context, completion_callback=self.callback_file_operation_complete, completion_data=self._max_id)
                button = gtk.Button()
                button.connect('clicked', self.callback_dnd_fops_complete, None, fileop)
                self._file_operations[self._max_id] = fileop
                fileop.start()
                self._max_id += 1
            except:
                drag_context.finish(False, False, int(time.time()))

    def callback_file_operation_complete(self, id):
        self._lock_fileop.acquire()
        del self._file_operations[id]
        if self._main_window_closed:
            self.shutdown()
        self._lock_fileop.release()

    def callback_dnd_fops_complete(self, widget, event, drag_context=None):
        delete = False
        if drag_context.action == gtk.gdk.ACTION_MOVE:
            delete = True
        drag_context.finish(True, delete, int(time.time()))

    def callback_dnd_drop(self, widget, drag_context, x, y, timestamp, params=None):
        return True

    def callback_dnd_end(self, widget, drag_context, params=None):
        pass

    def callback_dnd_failed(self, widget, drag_context, result, params=None):
        pass

    def callback_dnd_leave(self, widget, drag_context, timestamp, params=None):
        pass

    def callback_dnd_motion(self, widget, drag_context, x, y, timestamp, params=None):
        pass

    def callback_key_pressed(self, widget, event, data=None):
        if event.state == 0:
            if event.keyval == gtk.keysyms.Delete:
                self.delete_selected_files()
                return True
        return False

    def callback_key_released(self, widget, event, data=None):
        pass

    def callback_row_activated(self, treeview, path, column, user_data=None):
        index = self._columns['name']['index']
        model = self.treestore
        iter = model.get_iter(path)
        name = model.get_value(iter, index)
        self.path.step_in(name)
        self.update()

    def callback_path_updated(self):
        if not self._lock_path.acquire(0):
            return
        self.update()
        self._lock_path.release()

# ===== Sorting Methods ===================================
    def sort_files(self, treemodel, iter1, iter2, user_data=None):
        name_idx = self._columns['name']['index']
        mode_idx = self._columns['mode']['index']
        if self._folders_first:
            folder1 = stat.S_ISDIR(treemodel.get_value(iter1, mode_idx))
            folder2 = stat.S_ISDIR(treemodel.get_value(iter2, mode_idx))
            if folder1 != folder2:
                if folder1:
                    return -1
                else:
                    return 1
        return cmp(treemodel.get_value(iter1, name_idx), treemodel.get_value(iter2, name_idx))


# ===== General Methods ==============================================
    def delete_selected_files(self):
        refs = self.get_selected_files()
        model = self.treestore
        uris = []
        index = self._columns['name']['index']
        for ref in refs:
            path = ref.get_path()
            iter = model.get_iter(path)
            name = model.get_value(iter, index)
            uris.append(name)
            model.remove(iter)

    def delete_files(self, uris):
        fileop = FileOperation(action, uris, self.path.get_path(), drag_context)
        button.connect('clicked', self.callback_dnd_fops_complete, None, fileop)
        fileop.start()
        button = None
        fileop = None

    def get_selected_files(self):
        selection = self.treeview.get_selection().get_selected_rows()
        refs = []
        model = self.treestore
        for path in selection[1]:
            refs.append(gtk.TreeRowReference(model, path))
        return refs

    def shutdown(self):
        self._lock_shutdown.acquire()
        self._main_window_closed = True
        if not len(self._file_operations.items()):
            gtk.main_quit()
        self._lock_shutdown.release()

    def update(self):
        try:
            path = self.path.get_path()
            files = os.listdir(path)
            model = self.treestore
            model.clear()
            for file in files:
                file_path = os.path.abspath(path + '/' + file)
                properties = os.lstat(file_path)
                mode = properties[0]
                type = 'file'
                if stat.S_ISDIR(mode):
                    type = 'directory'
                elif stat.S_ISBLK(mode):
                    type = 'block-device'
                elif stat.S_ISCHR(mode):
                    type = 'character-device'
                elif stat.S_ISFIFO(mode):
                    type = 'named-pipe'
                elif stat.S_ISSOCK(mode):
                    type = 'socket'
                elif stat.S_ISLNK(mode):
                    properties = os.stat(file_path)
                    mode = properties[0]
                    if stat.S_ISREG(mode):
                        type = 'link-to-file'
                    elif stat.S_ISDIR(mode):
                        type = 'link-to-directory'
                    elif stat.S_ISBLK(mode):
                        type = 'link-to-block-device'
                    elif stat.S_ISCHR(mode):
                        type = 'link-to-character-device'
                    elif stat.S_ISFIFO(mode):
                        type = 'link-to-named-pipe'
                    elif stat.S_ISSOCK(mode):
                        type = 'link-to-socket'
                    elif stat.S_ISLNK(mode):
                        type = 'link-to-link'
                    
                icon = self.get_icon(type)
                permissions = self.get_permissions(stat.S_IMODE(mode))
                args = [icon,file,type,permissions]
                args.extend(list(properties))
                model.append(None, args)
            self.treestore.set_sort_column_id(self._columns['name']['index'], self._sort_order)
            #self.treestore.sort_column_changed()
        except TypeError, e:
            print "TypeError:", str(e)
            raise

    def get_icon(self, type):
        if self._icons.has_key(type):
            return self._icons[type]
        if   type == 'directory':                id = ('folder',      None)
        elif type == 'block-device':             id = ('blockdevice', None)
        elif type == 'character-device':         id = ('chardevice',  None)
        elif type == 'named-pipe':               id = ('pipe',        None)
        elif type == 'socket':                   id = ('socket',      None)
        elif type == 'link-to-directory':        id = ('folder',      'link_overlay')
        elif type == 'link-to-file':             id = ('file',        'link_overlay')
        elif type == 'link-to-link':             id = ('file_broken', 'link_overlay')
        elif type == 'link-to-block-device':     id = ('blockdevice', 'link_overlay')
        elif type == 'link-to-character-device': id = ('chardevice',  'link_overlay')
        elif type == 'link-to-named-pipe':       id = ('pipe',        'link_overlay')
        elif type == 'link-to-socket':           id = ('socket',      'link_overlay')
        else:                                    id = ('file',        None)
        icon = asl.new_icon(id[0])
        if id[1] is not None:
            pixmap,mask = icon.render_pixmap_and_mask(alpha_threshold=127)
            width,height = pixmap.get_size()
            overlay = asl.new_icon(id[1])
            pixmap.draw_pixbuf(None, overlay, 0, 0, 0, 0, width, height)
            icon = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, True, 8, width, height)
            icon.get_from_drawable(pixmap, self.window.get_colormap(), 0, 0, 0, 0, width, height)
        self._icons[type] = icon.scale_simple(self._icon_width, self._icon_height, gtk.gdk.INTERP_HYPER)
        return icon

    def get_permissions(self, permissions):
        string = ''
        if permissions & stat.S_IRUSR: string += 'r'
        else: string += '-'
        if permissions & stat.S_IWUSR: string += 'w'
        else: string += '-'
        if permissions & stat.S_IXUSR: string += 'x'
        else: string += '-'
        if permissions & stat.S_IRGRP: string += 'r'
        else: string += '-'
        if permissions & stat.S_IWGRP: string += 'w'
        else: string += '-'
        if permissions & stat.S_IXGRP: string += 'x'
        else: string += '-'
        if permissions & stat.S_IRGRP: string += 'r'
        else: string += '-'
        if permissions & stat.S_IWGRP: string += 'w'
        else: string += '-'
        if permissions & stat.S_IXGRP: string += 'x'
        else: string += '-'
        return string
#/*}}}*/

# === FileManager Class/*{{{*/
class FileManager(StatefulClass):
    def __init__(self):
        StatefulClass.__init__(self, os.path.abspath(asl.home_directory + '/.file_manager.db'))
        self.load_state()

# ===== GUI Build-up ========================================
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title("File Manager")
        self.window.set_icon(asl.new_icon('file_manager'))

        self.vbox_main = gtk.VBox()
        self.files = FileWidget()

# ===== Layout Configuration ==============================================
        self.window.add(self.vbox_main)
        self.vbox_main.pack_start(self.files,   True,  True, 2)

# ===== Attribute Configuration ===========================================

# ===== Event Bindings
        self.window.connect("destroy-event", self.callback_quit, None)
        self.window.connect("delete-event",  self.callback_quit, None)
        self.window.connect("configure-event", self.callback_window_configured, None )
        self.window.connect("screen-changed", self.callback_window_configured, None )
        self.window.connect("window-state-event", self.callback_window_configured, None )
        self.window.connect("key-press-event", self.callback_key_pressed)

        self.window.show_all()

        g = self.recall_value('window-gravity')
        if g: self.window.set_gravity(int(g))
        #coordinates = self.recall_value('window-position')
        #if coordinates: self.window.move(*map(int,coordinates.split(',',1)))
        dimensions = self.recall_value('window-size')
        if dimensions: self.window.resize(*map(int,dimensions.split(',',1)))
        fullscreen = self.recall_value('window-fullscreen')
        #if fullscreen == 'TRUE':
        #    self.window.fullscreen()
        #else:
        #    self.window.unfullscreen()

# ===== Callback Methods =============================================
    def callback_key_pressed(self, widget, event, data=None):
        if event.state == gtk.gdk.CONTROL_MASK:
            if event.keyval == ord('q'):
                self.close_application(widget, event, data)
                return True
        if event.state == gtk.gdk.MOD1_MASK:
            if event.keyval == ord('q'):
                self.close_application(widget, event, data)
                return True
        return False

    def callback_quit(self, widget, event, data=None):
        self.close_application(widget, event, data)

    def callback_window_configured(self, widget, event, data=None):
        gravity  = str(int(self.window.get_gravity()))
        position = '%d,%d' % self.window.get_position()
        size     = '%d,%d' % self.window.get_size()
        self.store_value('window-gravity', gravity)
        #self.store_value('window-position', position)
        self.store_value('window-size', size)
        #if event.type == gtk.gdk.WINDOW_STATE:
        #    if event.new_window_state == gtk.gdk.WINDOW_STATE_MAXIMIZED:
        #        self.store_value('window-fullscreen', 'TRUE')
        #    else:
        #        self.store_value('window-fullscreen', 'FALSE')

    def close_application(self, widget, event, data=None):
        self.window.hide()
        self.save_state()
        self.files.shutdown()
        return False
#/*}}}*/

def main():
    manager = FileManager()
    gtk.main()
        
if __name__ == '__main__':
    try: 
        import psyco
        psyco.full()
    except: pass
    main()

