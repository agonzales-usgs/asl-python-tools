#!/usr/bin/env python
import glob
import optparse
import os 
import re
import stat
import sys

TYPE_DEFAULT = 0
TYPE_DIR     = 1
TYPE_FILE    = 2
TYPE_ALL     = 3

SMART_NONE   = 0
SMART_GROUP  = 1
SMART_ALL    = 2

ACTION_DISABLE   = 0
ACTION_ENABLE    = 1
ACTION_IGNORE    = 2
ACTION_PROPOGATE = 3

def T(e,a,b):
    if e: return a
    else: return b

def code_to_action(code):
    if code == 'D': return ACTION_DISABLE
    if code == 'E': return ACTION_ENABLE
    if code == 'I': return ACTION_IGNORE
    if code == 'P': return ACTION_PROPOGATE
    raise ValueError("Invalid action code")

class Permissions(object):
    def __init__(self, mask='IIIIIIIII', depth=-1, type=TYPE_DEFAULT, verbosity=0):
        object.__init__(self)

        self._mask      = mask
        self._depth     = depth
        self._type      = type
        self._verbosity = verbosity

        self._user_read   = code_to_action(mask[0])
        self._user_write  = code_to_action(mask[1])
        self._user_exec   = code_to_action(mask[2])
        self._group_read  = code_to_action(mask[3])
        self._group_write = code_to_action(mask[4])
        self._group_exec  = code_to_action(mask[5])
        self._other_read  = code_to_action(mask[6])
        self._other_write = code_to_action(mask[7])
        self._other_exec  = code_to_action(mask[8])

    def process(self, path_list):
        for path in path_list:
            path = os.path.abspath(path)
            if not os.path.exists(path):
                print "%s: path not found" % path
            else:
                self._process_path(path, self._depth)

    def _process_path(self, path, depth):
        if depth == 0: return
        if not os.path.exists(path):
            print "%s: path not found" % path
        if os.path.isdir(path):
            try:
                for extension in os.listdir(path):
                    self._process_path(os.path.abspath(path + '/' + extension), depth - 1)
            except OSError, e:
                print "%s: cannot read directory contents, permission denied" % path
        self._edit_permissions(path)

    def _edit_permissions(self, path):
        file_stat = os.stat(path)
        mode = file_stat[stat.ST_MODE]
        if stat.S_ISDIR(mode):
            if (self._type == TYPE_FILE):
                if self._verbosity > 0:
                    print "skipping directory '%s'" % path
                return
        if stat.S_ISREG(mode):
            if (self._type == TYPE_DIR):
                if self._verbosity > 0:
                    print "skipping regular file '%s'" % path
                return
        if stat.S_ISCHR(mode):
            if (self._type != TYPE_ALL):
                if self._verbosity > 0:
                    print "skipping character device '%s'" % path
                return
        if stat.S_ISBLK(mode):
            if (self._type != TYPE_ALL):
                if self._verbosity > 0:
                    print "skipping block device '%s'" % path
                return
        if stat.S_ISFIFO(mode):
            if (self._type != TYPE_ALL):
                if self._verbosity > 0:
                    print "skipping fifo '%s'" % path
                return
        if stat.S_ISLNK(mode):
            if (self._type != TYPE_ALL):
                if self._verbosity > 0:
                    print "skipping symbolic link '%s'" % path
                return
        if stat.S_ISSOCK(mode):
            if (self._type != TYPE_ALL):
                if self._verbosity > 0:
                    print "skipping socket '%s'" % path
                return
        self._set_permissions(path, mode)

    def _set_permissions(self, path, mode):
        new_mode = mode

        # User Read
        if self._user_read == ACTION_DISABLE:
            new_mode &= ~stat.S_IRUSR
        elif self._user_read == ACTION_ENABLE:
            new_mode |= stat.S_IRUSR

        # User Write
        if self._user_write == ACTION_DISABLE:
            new_mode &= ~stat.S_IWUSR
        elif self._user_write == ACTION_ENABLE:
            new_mode |= stat.S_IWUSR

        # User Exec
        if self._user_exec == ACTION_DISABLE:
            new_mode &= ~stat.S_IXUSR
        elif self._user_exec == ACTION_ENABLE:
            new_mode |= stat.S_IXUSR

        # Group Read
        if self._group_read == ACTION_DISABLE:
            new_mode &= ~stat.S_IRGRP
        elif self._group_read == ACTION_ENABLE:
            new_mode |= stat.S_IRGRP
        elif self._group_read == ACTION_PROPOGATE:
            if new_mode & stat.S_IRUSR:
                new_mode |= stat.S_IRGRP
            else:
                new_mode &= ~stat.S_IRGRP

        # Group Write
        if self._group_write == ACTION_DISABLE:
            new_mode &= ~stat.S_IWGRP
        elif self._group_write == ACTION_ENABLE:
            new_mode |= stat.S_IWGRP
        elif self._group_write == ACTION_PROPOGATE:
            if new_mode & stat.S_IWUSR:
                new_mode |= stat.S_IWGRP
            else:
                new_mode &= ~stat.S_IWGRP

        # Group Exec
        if self._group_exec == ACTION_DISABLE:
            new_mode &= ~stat.S_IXGRP
        elif self._group_exec == ACTION_ENABLE:
            new_mode |= stat.S_IXGRP
        elif self._group_exec == ACTION_PROPOGATE:
            if new_mode & stat.S_IXUSR:
                new_mode |= stat.S_IXGRP
            else:
                new_mode &= ~stat.S_IXGRP

        # Other Read
        if self._other_read == ACTION_DISABLE:
            new_mode &= ~stat.S_IROTH
        elif self._other_read == ACTION_ENABLE:
            new_mode |= stat.S_IROTH
        elif self._other_read == ACTION_PROPOGATE:
            if new_mode & stat.S_IRGRP:
                new_mode |= stat.S_IROTH
            else:
                new_mode &= ~stat.S_IROTH

        # Other Write
        if self._other_write == ACTION_DISABLE:
            new_mode &= ~stat.S_IWOTH
        elif self._other_write == ACTION_ENABLE:
            new_mode |= stat.S_IWOTH
        elif self._other_write == ACTION_PROPOGATE:
            if new_mode & stat.S_IWGRP:
                new_mode |= stat.S_IWOTH
            else:
                new_mode &= ~stat.S_IWOTH

        # Other Exec
        if self._other_exec == ACTION_DISABLE:
            new_mode &= ~stat.S_IXOTH
        elif self._other_exec == ACTION_ENABLE:
            new_mode |= stat.S_IXOTH
        elif self._other_exec == ACTION_PROPOGATE:
            if new_mode & stat.S_IXGRP:
                new_mode |= stat.S_IXOTH
            else:
                new_mode &= ~stat.S_IXOTH

        if mode == new_mode:
            if self._verbosity > 0:
                print "Mode [%s] is unchanged for '%s'" % (mode_to_text(mode), path)
        else:
            new_imode = stat.S_IMODE(new_mode)
            try:
                os.chmod(path, new_imode)
            except OSError, e:
                print "Cannot not change mode for '%s', permission denied" % path
            if self._verbosity > 0:
                print "Mode changed from [%s] to [%s] for '%s'" % (mode_to_text(mode), mode_to_text(new_mode), path)

def mode_to_text(mode):
    mode_str = ''
    if stat.S_ISDIR(mode):    mode_str += 'd'
    elif stat.S_ISCHR(mode):  mode_str += 'c'
    elif stat.S_ISBLK(mode):  mode_str += 'b'
    elif stat.S_ISFIFO(mode): mode_str += 'p'
    elif stat.S_ISLNK(mode):  mode_str += 'l'
    elif stat.S_ISSOCK(mode): mode_str += 's'
    #elif stat.S_ISREG(mode):  mode_str += '-'
    else:  mode_str += '-'
    mode_str += T(mode & stat.S_IRUSR,'r','-')
    mode_str += T(mode & stat.S_IWUSR,'w','-')
    if stat.S_ISUID & mode:
        mode_str += T(mode & stat.S_IXUSR,'s','S')
    else:
        mode_str += T(mode & stat.S_IXUSR,'x','-')
    mode_str += T(mode & stat.S_IRGRP,'r','-')
    mode_str += T(mode & stat.S_IWGRP,'w','-')
    if stat.S_ISGID & mode:
        mode_str += T(mode & stat.S_IXGRP,'s','S')
    else:
        mode_str += T(mode & stat.S_IXGRP,'x','-')
    mode_str += T(mode & stat.S_IROTH,'r','-')
    mode_str += T(mode & stat.S_IWOTH,'w','-')
    if stat.S_ISVTX & mode:
        mode_str += T(mode & stat.S_IXOTH,'t','T')
    else:
        mode_str += T(mode & stat.S_IXOTH,'x','-')
    return mode_str

class Main:
    def __init__(self):
        option_list = []
        option_list.append(optparse.make_option("-A", "--all-types", dest="all_types", action="store_true", help="change file objects of any type (includes devices)"))
        option_list.append(optparse.make_option("-d", "--depth", dest="depth", action="store", type="int", help="recurse this many levels (includes current level)"))
        option_list.append(optparse.make_option("-D", "--directories-only", dest="directories_only", action="store_true", help="only change permissions on directories"))
        option_list.append(optparse.make_option("-F", "--files-only", dest="files_only", action="store_true", help="only change permissions on regular files"))
        option_list.append(optparse.make_option("-g", "--group", dest="group", action="store", metavar="control_mask", help="control_mask for the group"))
        option_list.append(optparse.make_option("-o", "--other", dest="other", action="store", metavar="control_mask", help="control_mask for all others"))
        option_list.append(optparse.make_option("-s", "--smart", dest="smart", action="store_true", help="use smart options (mask 'PIP') for group"))
        option_list.append(optparse.make_option("-S", "--smart-all", dest="smart_all", action="store_true", help="use smart options (mask 'PIP') for group and other"))
        option_list.append(optparse.make_option("-u", "--user", dest="user", action="store", metavar="control_mask", help="control_mask for the owner"))
        option_list.append(optparse.make_option("-v", dest="verbosity", action="count", help="specify multiple times to increase verbosity"))
        self.parser = optparse.OptionParser(option_list=option_list)
        self.parser.set_usage("""Usage: %prog [options] [path1 [path2 ...]]

The control_mask is a three character mask with positions mapping to rwx with 
each character being one of (D,E,I,P) where D disables the permission, 
E enables the permission, I ignores parent permissions (keeps current 
permission), P propogates the permission of the next highest privilege level. 
For example, if the user supplies the option --other=EIP, the read permission 
will always be enabled, the write permission will use the existing will not 
change, and the execute permission will be the same as that of the group.""")

    def usage(self, message=''):
        if message != '':
            print "E:", message
        self.parser.print_help()
        sys.exit(1)

    def start(self):
        self.options, self.args = self.parser.parse_args()

        regex_mask = re.compile('^[DEIP]{3}$')

        arg_other = 'III'
        arg_group = 'III'
        arg_user  = 'III'
        depth     = -1 # No limit
        arg_type  = TYPE_DEFAULT
        arg_smart = SMART_NONE
        verbosity = 0

        if self.options.smart:
            if arg_smart > 0:
                self.usage("You may only supply one of -s, -S")
            arg_smart = SMART_GROUP

        if self.options.smart_all:
            if arg_smart > 0:
                self.usage("You may only supply one of -s, -S")
            arg_smart = SMART_ALL

        if arg_smart == SMART_GROUP:
            arg_group = 'PIP'
        elif arg_smart == SMART_ALL:
            arg_group = 'PIP'
            arg_other = 'PIP'

        if self.options.other:
            arg_other = self.options.other
            if len(arg_other) != 3:
                self.usage()
            if not regex_mask.match(arg_other):
                self.usage()

        if self.options.group:
            arg_group = self.options.group
            if len(arg_group) != 3:
                self.usage()
            if not regex_mask.match(arg_group):
                self.usage()

        if self.options.user:
            arg_user = self.options.user
            if len(arg_user) != 3:
                self.usage()
            if not regex_mask.match(arg_user):
                self.usage()
        
        mask = arg_user + arg_group + arg_other

        if self.options.depth:
            depth = self.options.depth

        if self.options.directories_only:
            if arg_type > 0:
                self.usage("You may only supply one of -A, -D, -F")
            arg_type = TYPE_DIR
        
        if self.options.files_only:
            if arg_type > 0:
                self.usage("You may only supply one of -A, -D, -F")
            arg_type = TYPE_FILE

        if self.options.all_types:
            if arg_type > 0:
                self.usage("You may only supply one of -A, -D, -F")
            arg_type = TYPE_ALL

        if self.options.verbosity:
            verbosity = self.options.verbosity

        Permissions(mask, depth, arg_type, verbosity).process(self.args)

if __name__ == '__main__':
    try:
        Main().start()
    except KeyboardInterrupt:
        print

