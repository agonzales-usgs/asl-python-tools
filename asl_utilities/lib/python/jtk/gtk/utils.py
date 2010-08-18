import pygtk
pygtk.require('2.0')
import gtk
import gobject

def seed_file_filters():
    filters = []
    for (name, patterns) in [('All Files',        ['*']),
                             ('MiniSEED Files',   ['*.[Ss][Ee][Ee][Dd]']),
                             ('Circular Buffers', ['*.[Bb][Uu][Ff]']),
                            ]:
        filter = gtk.FileFilter()
        filter.set_name(name)
        for pattern in patterns:
            filter.add_pattern(pattern)
        filters.append(filter)
    return filters

file_filters = {
    'none' : None,
    'seed' : seed_file_filters,
}

def get_filters(filter_id):
    try:
        return file_filters[filter_id]()
    except:
        return []

def select_save_file(current_dir='.', filter_id='none'):
    file = ''
    file_chooser = gtk.FileChooserDialog("Select File", None,
                                         gtk.FILE_CHOOSER_ACTION_SAVE,
                                         (gtk.STOCK_CANCEL,
                                          gtk.RESPONSE_CANCEL,
                                          gtk.STOCK_OPEN,
                                          gtk.RESPONSE_OK))
    file_chooser.set_default_response(gtk.RESPONSE_OK)
    file_chooser.set_current_folder(current_dir)
    file_chooser.set_select_multiple(False)
    for filter in get_filters(filter_id):
        file_chooser.add_filter(filter)
    result = file_chooser.run()
    if result == gtk.RESPONSE_OK:
        file = file_chooser.get_filename()
    file_chooser.destroy()
    return file

def select_file(current_dir='.', filter_id='none'):
    return select_files(current_dir, False, filter_id)

def select_files(current_dir='.', multiple=True, filter_id='none'):
    if multiple:
        files = []
    else:
        files = ''
    file_chooser = gtk.FileChooserDialog("Select Files", None,
                                         gtk.FILE_CHOOSER_ACTION_OPEN,
                                         (gtk.STOCK_CANCEL,
                                          gtk.RESPONSE_CANCEL,
                                          gtk.STOCK_OPEN,
                                          gtk.RESPONSE_OK))
    file_chooser.set_default_response(gtk.RESPONSE_OK)
    file_chooser.set_current_folder(current_dir)
    file_chooser.set_select_multiple(multiple)
    for filter in get_filters(filter_id):
        file_chooser.add_filter(filter)
    result = file_chooser.run()
    if result == gtk.RESPONSE_OK:
        if multiple:
            files = file_chooser.get_filenames()
        else:
            files = file_chooser.get_filename()
    file_chooser.destroy()
    return files

def select_directory(current_dir='.'):
    return select_directories(current_dir, False)

def select_directories(current_dir='.', multiple=True):
    if multiple:
        directories = []
    else:
        directories = ''
    dir_chooser = gtk.FileChooserDialog("Select Directory", None,
                                         gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                                         (gtk.STOCK_CANCEL,
                                          gtk.RESPONSE_CANCEL,
                                          gtk.STOCK_OPEN,
                                          gtk.RESPONSE_OK))
    dir_chooser.set_default_response(gtk.RESPONSE_OK)
    dir_chooser.set_current_folder(current_dir)
    dir_chooser.set_select_multiple(multiple)
    result = dir_chooser.run()
    if result == gtk.RESPONSE_OK:
        if multiple:
            directories = dir_chooser.get_filenames()
        else:
            directories = dir_chooser.get_filename()
    dir_chooser.destroy()
    return directories


def LEFT(widget):
    a = gtk.Alignment(xalign=0.0)
    a.add(widget)
    return a

def RIGHT(widget):
    a = gtk.Alignment(xalign=1.0)
    a.add(widget)
    return a

def CENTER(widget):
    a = gtk.Alignment(xalign=0.5)
    a.add(widget)
    return a

