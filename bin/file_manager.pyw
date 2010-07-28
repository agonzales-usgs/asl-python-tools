#!/usr/bin/env python
import asl

import calendar
import glob
import optparse
import os
import Queue
import re
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
            column = {}
            tvc = gtk.TreeViewColumn(title)
            if attribute == 'pixbuf':
                cr = gtk.CellRendererPixbuf()
            else:
                cr = gtk.CellRendererText()
            tvc.pack_start(cr, True)
            tvc.add_attribute(cr, attribute, idx)
            tvc.set_cell_data_func(cr, self.cdf_format_files, (id,attribute))

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

        self.path.set_path('.')

        self.treeview.connect("row-activated", self.callback_row_activated, None)

        self.path_lock = threading.Lock()

        self.show_all()
        self.update()

    def cdf_format_files(self, column, cell, model, iter, data=None):
        id,attr = data
        if attr == 'text':
            cell.set_property("foreground", "#000000")

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

    def filter_files(self, model, iter, data=None):
        for id in self._columns.keys():
            regex = self._columns[id]['regex'] 
            index = self._columns[id]['index']
            value = model.get_value(iter, index)
            if value and regex and not regex.search(value):
                return False
        return True

    def callback_filter_focus_out(self, widget, event, data=None):
        self.filter_hint_show(widget)

    def callback_filter_focus_in(self, widget, event, data=None):
        self.filter_hint_hide(widget)

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

