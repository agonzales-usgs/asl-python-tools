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

import pygtk
pygtk.require('2.0')
import gtk
import gobject
import pango
gobject.threads_init()

from jtk.Thread import Thread
from jtk.Logger import LogThread
from jtk.StatefulClass import StatefulClass

FILTER_NONE  = 0
FILTER_ENTRY = 1
FILTER_COMBO = 2

COLUMN_HIDE = False
COLUMN_SHOW = True

DND_URI_TUPLE = ("text/uri-list", 0, 25)
#DND_FILESOURCE_TUPLE = ("pitivi/file-source", 0, 26)

FO_COPY_ERROR = 0
FO_MOVE_ERROR = 1
FO_LINK_ERROR = 2

class FileOperation(Thread):
    def __init__(self, action, file_list, context=None):
        self.progress_queue = Queue.Queue()

        self.window = gtk.Window()
        self.window.set_title("File Operation")
        self.window.set_icon(asl.new_icon('file_manager'))

        self.hbox = gtk.HBox()
        self.progress = gtk.ProgressBar()
        self.button_cancel = gtk.Button(stock=gtk.STOCK_CANCEL)

        self.window.add(self.hbox)
        self.hbox.pack_start(self.progress,      False, True,  2)
        self.hbox.pack_start(self.button_cancel, False, False, 2)

        self.button_cancel.connect("clicked", self.callback_cancel, None)

        self.hbutton_progress = gtk.Button()
        self.hbutton_progress.connect("clicked", self.callback_update_progress, None)

        self.window.show_all()

        self.action = action
        self.file_list = file_list
        self.context = context

    def __del__(self):
        self.window.hide()
        del self.window

    def get_context(self):
        return self.context

    def set_context(self, context):
        self.context = context

    def callback_cancel(self, widget, event, data=None):
        self.halt_now()

    def callback_update_progress(self, widget, event, data=None):
        try:
            progress,total = self.progress_queue.get()
            self.progress_queue.task_done()
            self.progress.set_text("processing file %d of %d" % (progress,total))
            self.progress.set_fraction(float(progress)/float(total))
        except Queue.Empty:
            pass

    def update_progress(self, progress, total):
        self.progress_queue.put((progress,total))
        gobject.idle_add(gobject.GObject.emit, self.hbutton_progress, 'clicked')

    def _pre(self):
        # Fill queue here? How else do we plan to get the files in?
        for file in file_list:
            self.queue.put(file)

    def _run(self, message, data):
        # TODO:
        # Perhaps we should be handling the process rather than
        # using language utilities...
        src,dst = data
        if message == gtk.gdk.ACTION_COPY:
            try:
                shutil.copytree(src, dst)
            except:
                raise FO_COPY_ERROR
        elif message == gtk.gdk.ACTION_MOVE:
            try:
                shutil.move(src, dst)
            except:
                raise FO_MOVE_ERROR
        elif message == gtk.gdk.ACTION_LINK:
            try:
                os.symlink(source, dst)
            except:
                raise FO_LINK_ERROR
        time.sleep(0.5)


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


#class DragTreeStore(gtk.TreeStore):
#    def __init__(self):
#        gtk.TreeStore.__init__(self)
#
#    def drag_data_get(path, selection_data):
#        uris = []
#        refs = self.get_selected_files()
#        model = self.treestore.get_model()
#        directory = self.path.get_path()
#        index = self._columns['name']['index']
#        for ref in refs:
#            path = ref.get_path()
#            iter = model.get_iter(path)
#            name = model.get_value(iter, index)
#            uris.append(os.path.abspath(directory + '/' + name))
#        if info == DND_URI_TUPLE[-1]:
#            selection_data.set(selection_data.target, 8, '\n'.join(uris))
#
#    def drag_data_delete(path):


class FileWidget(gtk.VBox):
    def __init__(self):
        gtk.VBox.__init__(self)

        #self._root = os.path.abspath('/data/temp_data')

        self._column_defs = [
            ('icon',    '',             gtk.gdk.Pixbuf,      'pixbuf',  COLUMN_SHOW, FILTER_NONE),
            ('name',    'Name',         gobject.TYPE_STRING, 'text',    COLUMN_SHOW, FILTER_ENTRY),
            ('type',    'Type',         gobject.TYPE_STRING, 'text',    COLUMN_SHOW, FILTER_NONE),
            ('perm',    'Permissions',  gobject.TYPE_STRING, 'text',    COLUMN_SHOW, FILTER_NONE),
            ('mode',    'Mode',         gobject.TYPE_LONG,   'text',    COLUMN_HIDE, FILTER_NONE),
            ('ino',     'Inode',        gobject.TYPE_LONG,   'text',    COLUMN_HIDE, FILTER_NONE),
            ('dev',     'Device',       gobject.TYPE_LONG,   'text',    COLUMN_HIDE, FILTER_NONE),
            ('nlink',   'Link Count',   gobject.TYPE_LONG,   'text',    COLUMN_HIDE, FILTER_NONE),
            ('uid',     'User',         gobject.TYPE_LONG,   'text',    COLUMN_HIDE, FILTER_NONE),
            ('gid',     'Group',        gobject.TYPE_LONG,   'text',    COLUMN_HIDE, FILTER_NONE),
            ('size',    'Size',         gobject.TYPE_INT64,  'text',    COLUMN_SHOW, FILTER_NONE),
            ('atime',   'Accessed',     gobject.TYPE_LONG,   'text',    COLUMN_HIDE, FILTER_NONE),
            ('mtime',   'Modified',     gobject.TYPE_LONG,   'text',    COLUMN_HIDE, FILTER_NONE),
            ('ctime',   'Created',      gobject.TYPE_LONG,   'text',    COLUMN_HIDE, FILTER_NONE),
        ]

        self._icons = {}
        self._icon_width = 32
        self._icon_height = 32
        self._columns = {}
        self._sort_order = gtk.SORT_ASCENDING
        self._folders_first = True

# ===== GUI Build-up ========================================
        args = map(lambda c: c[2], self._column_defs)
        self.treestore = gtk.TreeStore(*args).filter_new()

        try:
            self.tooltips = gtk.Tooltips()
        except:
            self.tooltips = None

# ===== Widget Creation ============================================
        self.hbox_filters       = gtk.HBox()

        self.scroll_treeview    = gtk.ScrolledWindow()
        self.scroll_iconview    = gtk.ScrolledWindow()

        self.treeview           = gtk.TreeView(self.treestore)
        self.iconview           = gtk.IconView()

        self.scroll_iconview.add(self.iconview)
        self.scroll_treeview.add(self.treeview)

        idx = 0
        model = self.treestore.get_model()
        for id,title,type,attribute,show,filter in self._column_defs:
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
            if filter == FILTER_ENTRY:
                filter_widget = gtk.Entry()
                filter_widget._filter_title = title
                filter_widget.connect('changed',         self.callback_filter_changed,   None, id)
                filter_widget.connect('focus-in-event',  self.callback_filter_focus_in,  None)
                filter_widget.connect('focus-out-event', self.callback_filter_focus_out, None)
                self.filter_hint_show(filter_widget)
            else:
                filter_widget = None
            if filter_widget is not None:
                self.hbox_filters.pack_start(filter_widget, False, True, 2)
            column['filter']         = filter_widget
            column['regex']          = None

            if show:
                self.treeview.append_column(tvc)
            model.set_sort_func(idx, self.sort_files, id)
            idx += 1

        self.path = PathWidget(self.callback_path_updated)

        self.pack_start(self.path,              False, True,  2)
        self.pack_start(self.hbox_filters,      False, True,  2)
        self.pack_start(self.scroll_treeview,   True,  True,  2)

        self.treeview.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.scroll_iconview.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scroll_treeview.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.treestore.set_visible_func(self.filter_files)
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

        self.path_lock = threading.Lock()

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
        model = self.treestore.get_model()
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
                fileop = FileOperations(drag_context.action, uris, drag_context)
                button = gtk.Button()
                button.connect('clicked', self.callback_dnd_fops_complete, None, fileop)
                fileop.start()
                button = None
                fileop = None
                print "PROCESSING FILES"
            except:
                drag_context.finish(False, False, int(time.time()))

    def drag_data_received(self, treestore, dest, selection_data):
        print "OVERRIDDEN!"

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
        if event.keyval == gtk.keysyms.Delete:
            self.delete_selected_files()

    def callback_key_released(self, widget, event, data=None):
        pass

    def callback_row_activated(self, treeview, path, column, user_data=None):
        path = self.treestore.convert_path_to_child_path(path)
        index = self._columns['name']['index']
        model = self.treestore.get_model()
        iter = model.get_iter(path)
        name = model.get_value(iter, index)
        self.path.step_in(name)
        self.update()

    def callback_path_updated(self):
        if not self.path_lock.acquire(0):
            return
        self.update()
        self.path_lock.release()

    def callback_filter_changed(self, widget, event, id=None):
        text = widget.get_text()
        if text == widget._filter_title:
            text = ''
        regex = None
        if text == '':
            regex = None
        else:
            try: regex = re.compile(text, re.IGNORECASE)
            except: regex = None
        self._columns[id]['regex'] = regex
        self.treestore.refilter()
        filter_iter = self.treestore.get_iter_first()
        if filter_iter:
            iter = self.treestore.convert_iter_to_child_iter(filter_iter)
            if iter:
                path = self.treestore.get_model().get_path(iter)
                self.treeview.scroll_to_cell(path)

    def callback_filter_focus_out(self, widget, event, data=None):
        self.filter_hint_show(widget)

    def callback_filter_focus_in(self, widget, event, data=None):
        self.filter_hint_hide(widget)

# ===== Filter and Sorting Methods ===================================
    def filter_files(self, model, iter, data=None):
        for id in self._columns.keys():
            regex = self._columns[id]['regex'] 
            index = self._columns[id]['index']
            value = model.get_value(iter, index)
            if value and regex and not regex.search(value):
                return False
        return True

    def filter_hint_show(self, widget):
        if not len(widget.get_text()):
            widget.set_text(widget._filter_title)
            widget.modify_text(gtk.STATE_NORMAL, gtk.gdk.color_parse('#888888'))

    def filter_hint_hide(self, widget):
        if widget.get_text() == widget._filter_title:
            widget.set_text('')
        widget.modify_text(gtk.STATE_NORMAL, gtk.gdk.Color())

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
        model = self.treestore.get_model()
        #index = self._columns['name']['index']
        for ref in refs:
            path = ref.get_path()
            iter = model.get_iter(path)
            #name = model.get_value(iter, index)
            #print "deleting", name
            model.remove(iter)

    def get_selected_files(self):
        selection = self.treeview.get_selection().get_selected_rows()
        refs = []
        model = self.treestore.get_model()
        filter = self.treestore
        for filter_path in selection[1]:
            path = filter.convert_path_to_child_path(filter_path)
            refs.append(gtk.TreeRowReference(model, path))
        return refs

    def update(self):
        try:
            path = self.path.get_path()
            files = os.listdir(path)
            model = self.treestore.get_model()
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
            self.treestore.get_model().set_sort_column_id(self._columns['name']['index'], self._sort_order)
            #self.treestore.get_model().sort_column_changed()
            self.treestore.refilter()
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

        g = int(self.recall_value('window-gravity'))
        if g: self.window.set_gravity(g)
        coordinates = self.recall_value('window-position')
        if coordinates: self.window.move(*map(int,coordinates.split(',',1)))
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
        self.store_value('window-position', position)
        self.store_value('window-size', size)
        #if event.type == gtk.gdk.WINDOW_STATE:
        #    if event.new_window_state == gtk.gdk.WINDOW_STATE_MAXIMIZED:
        #        self.store_value('window-fullscreen', 'TRUE')
        #    else:
        #        self.store_value('window-fullscreen', 'FALSE')

    def close_application(self, widget, event, data=None):
        self.save_state()
        gtk.main_quit()
        return False

def main():
    manager = FileManager()
    gtk.main()
        
if __name__ == '__main__':
    main()

