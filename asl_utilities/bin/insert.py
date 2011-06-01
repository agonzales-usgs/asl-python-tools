#!/usr/bin/env python
# @author   Joel Edwards <jdedwards@usgs.gov>

"""
Copyright 2011, United States Geological Survey or
third-party contributors as indicated by the @author tags.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import optparse
import os
import re
import shutil
import sys

CONTENT_NONE = 0
CONTENT_TEXT = 1
CONTENT_FILE = 2

NONE = 0
LINE = 1
BYTE = 2

class Insert:
    def __init__(self, paths, content, depth=1, regex=None, index=0, clip=-1, line=True, extension='.save', prefix='', delete_save=False, verbosity=1):
        self.paths = paths
        self.content = content
        self.depth = depth
        self.regex = regex
        self.index = index
        self.clip = clip
        self.line = line
        self.extension = extension
        self.prefix = prefix
        self.delete_save = delete_save
        self.verbosity = verbosity

    def insert_content(self, filename):
        dir = os.path.dirname(filename)
        file = os.path.basename(filename)
        save_test = os.path.join(dir, self.prefix + file + self.extension)
        count = 0
        # Search for a free save file name
        while os.path.exists(save_test):
            count += 1
            save_test = os.path.join(dir, self.prefix + file + "." + str(count) + self.extension)
        save = save_test

        shutil.move(filename, save)
        rh = open(save, 'r')
        wh = open(filename, 'w+')
        
        # Skip over content we have been instructed to clip
        if self.clip > 0:
            if self.line:
                for i in range(0, self.clip):
                    rh.readline()
            else:
                rh.seek(self.clip, os.SEEK_CUR)

        # Copy the portion of the file before the start index
        if self.index > 0:
            if self.line:
                for i in range(0, self.index):
                    wh.write(rh.readline())
            else:
                wh.write(rh.read(self.index))

        # Write the insert content
        wh.write(self.content)

        # Write the rest of the file
        # TODO: FIX (This probably will not work for large files...)
        wh.write(rh.read())

        wh.close()
        rh.close()

    def file_matches(self, path):
        if self.regex is None:
            return True
        return self.regex.search(path) is not None

    def recurse(self, path, depth):
        if depth == 0:
            return
        if os.path.isdir(path):
            for name in os.path.listdir(path):
                new_path = os.path.join(path, name)
                self.recurse(new_path, self.depth - 1)
        elif not os.path.isfile(path):
            if self.verbosity > 0:
                print "Skipping non-regular file '%s'." % path
        elif not self.file_matches(path):
            if self.verbosity > 0:
                print "Skipping non-matching file '%s'." % path
        else:
            if self.verbosity > 0:
                print "Editing file '%s'." % path
            self.insert_content(path)

    def run(self):
        for path in self.paths:
            self.recurse(path, self.depth)


class Main:
    def __init__(self):
        option_list = []

        option_list.append(optparse.make_option("-b", "--byte-oriented", dest="byte_oriented", action="store_true", help="Index and clip operations are byte orientated instead of line oriented."))
        option_list.append(optparse.make_option("-c", "--clip", dest="clip", action="store", metavar="CLIP_COUNT", type="int", help="Remove the first CLIP_COUNT lines from the file. This is performed before the insertion."))
        option_list.append(optparse.make_option("-d", "--depth", dest="depth", action="store", type="int", help="Recurse this many levels for each matched path (includes current level). Enables recursion even without the -R flag, limits recursion even whith the -R flag."))
        option_list.append(optparse.make_option("-e", "--save-extension", dest="save_extension", action="store", metavar="EXTENSION", default=".insert.save", help="The original file will be renamed with the given extension. (compatible with -p flag)"))
        option_list.append(optparse.make_option("-f", "--content-file", dest="content_file", action="store", metavar="CONTENT_FILE", help="Read insert content from CONTENT_FILE."))
        option_list.append(optparse.make_option("-i", "--insert-index", dest="index", action="store", metavar="INDEX", type="int", help="Insert content before line/byte INDEX (indices start at zero). This is performed after any specified clip operation."))
        option_list.append(optparse.make_option("-m", "--match", dest="match", action="store", metavar="MATCH_REGEX", help="Only perform operation(s) on files which match this regular expression."))
        option_list.append(optparse.make_option("-p", "--save-prefix", dest="save_prefix", action="store", metavar="PREFIX", default="", help="The origintal file will be renamed with the given prefix (compatible with -e flag)."))
        option_list.append(optparse.make_option("-r", "--recursive", dest="recursive", action="store_true", help="Process the supplied path(s) recursively applying the operation(s) to all matching files."))
        option_list.append(optparse.make_option("-s", "--content-string", dest="content_string", action="store", metavar="STRING", help="Use STRING as the insert content."))
        option_list.append(optparse.make_option("-v", dest="verbosity", action="count", help="Specify multiple times to increase verbosity."))
        self.parser = optparse.OptionParser(option_list=option_list)
        self.parser.set_usage("""Usage: %prog [options] [path1 [path2 ...]]""")

    def error(self, message, usage=False):
        if message != '':
            print "E:", message
        if usage:
            self.parser.print_help()
        sys.exit(1)

    def usage(self, message=''):
        self.error(message, True)

    def start(self):
        self.options, self.args = self.parser.parse_args()

        arg_index           = -1
        arg_clip            = -1
        arg_recursive       = False
        arg_depth           = -1
        arg_verbosity       = 0
        arg_content_type    = CONTENT_NONE
        arg_content         = ""
        arg_line_oriented   = True
        arg_match_regex     = None
        arg_prefix          = ""
        arg_extension       = ""
        arg_delete_save     = False

        if self.options.recursive:
            arg_depth = -1
        if self.options.depth:
            arg_depth = self.options.depth
        if self.options.byte_oriented:
            arg_line_oriented = False

        if self.options.index:
            arg_index = self.options.index

        if self.options.save_prefix:
            arg_prefix = self.options.save_prefix
        if self.options.save_extension:
            arg_extension = self.options.save_extension

        if self.options.content_string:
            if arg_content_type > 0:
                self.usage("You may only supply one of -s, -f")
            arg_content_type = CONTENT_TEXT
            arg_content = self.options.content_string
        if self.options.content_file:
            if arg_content_type > 0:
                self.usage("You may only supply one of -s, -f")
            arg_content_type = CONTENT_FILE
            arg_content = self.options.content_file

        if self.options.match:
            try:
                arg_match_regex = re.compile(self.options.match)
            except:
                self.usage("Invalid value for -m option")

        if self.options.clip:
            arg_clip = self.options.clip

        if arg_content_type == CONTENT_FILE:
            if not os.path.exists(arg_content):
                self.error("Could not locate content file '%s'." % arg_content)
            elif not os.path.isfile(arg_content):
                self.error("Supplied content file path '%s' is not a regular file." % arg_content)
            else:
                arg_content = open(arg_content, 'r').read()

        if self.options.verbosity:
            verbosity = self.options.verbosity

        Insert(self.args, arg_content, arg_depth, arg_match_regex, arg_index, arg_clip, arg_line_oriented, arg_extension, arg_prefix, arg_delete_save, arg_verbosity).run()

if __name__ == '__main__':
    try:
        Main().start()
    except KeyboardInterrupt:
        print

