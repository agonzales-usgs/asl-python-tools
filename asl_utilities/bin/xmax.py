#!/usr/bin/env python
import asl

import glob     # for matching file patterns
import optparse # argument parsing
import os
import sys

from jtk import Config # generic key=value config file support

class Main:
    def __init__(self):
        option_list = []
        option_list.append(optparse.make_option(
            "-c", "--config-file", 
            dest="config_file", 
            action="store", 
            help="Path to config file for xmax launch script"))
        option_list.append(optparse.make_option(
            "-d", "--include-directories", 
            dest="include_directories", 
            action="store_true", 
            help="Symlinks should be created to matched directories"))
        option_list.append(optparse.make_option(
            "-j", "--join", 
            dest="join", 
            action="store_true", 
            help="Show all stations on the same page"))
        option_list.append(optparse.make_option(
            "-s", "--include-symlinks", 
            dest="include_symlinks", 
            action="store_true", 
            help="Symlinks should be created to matched symlinks"))
        option_list.append(optparse.make_option(
            "-t", "--use-temp-data", 
            dest="use_temp_data", 
            action="store_true", 
            help="include previously dumped temporary data with that in the selected path"))
        option_list.append(optparse.make_option(
            "-T", "--dump-temp-data", 
            dest="dump_temp_data", 
            action="store_true", 
            help="just dump temporary data, don't launch the display"))

        option_list.append(optparse.make_option(
            "-N", "--network", 
            dest="network", 
            action="store", 
            help="swmicolon-separated wildcard filter by network"))
        option_list.append(optparse.make_option(
            "-S", "--station", 
            dest="station", 
            action="store", 
            help="swmicolon-separated wildcard filter by station"))
        option_list.append(optparse.make_option(
            "-L", "--location", 
            dest="location", 
            action="store", 
            help="swmicolon-separated wildcard filter by location"))
        option_list.append(optparse.make_option(
            "-C", "--channel", 
            dest="channel", 
            action="store", 
            help="swmicolon-separated wildcard filter by channel"))
        self.parser = optparse.OptionParser(option_list=option_list)
        self.parser.set_usage("""Usage: %s [options] file_expr [file_expr ...] 

action: 
  file_expr - a glob expression specifying one or more files""" % (sys.argv[0].split('/')[-1],))

    def usage(self, message=''):
        if message != '':
            print "E:", message
        self.parser.print_help()
        sys.exit(1)


    def start(self):
        xmax_switches = {
        #   name           flag     arg?
            'config'        : ('-g',    True),
            'description'   : ('-i',    True),
            'earthquake'    : ('-k',    True),
            'picks'         : ('-p',    True),
            'quality'       : ('-q',    True),

            'display'       : ('-f',    True),
            'format'        : ('-F',    True),
            'unit'          : ('-u',    True),
            'order'         : ('-o',    True),

            'data'          : ('-d',    True),
            'block'         : ('-L',    True),
            'merge'         : ('-m',    False),
            'temp'          : ('-t',    False),
            'dump'          : ('-T',    False),

            'network'       : ('-n',    True),
            'station'       : ('-s',    True),
            'location'      : ('-l',    True),
            'channel'       : ('-c',    True),
        }

        xmax_options = {
        #   name          value (or False to exclude this option by default)
            'config'        : False,
            'description'   : False,
            'earthquake'    : False,
            'picks'         : False,
            'quality'       : False,

            'display'       : '1',
            'format'        : False,
            'order'         : False,
            'unit'          : '1',

            'data'          : False,
            'block'         : False,
            'merge'         : False,
            'temp'          : False,
            'dump'          : False,

            'network'       : False,
            'station'       : False,
            'location'      : False,
            'channel'       : False,

            'begin'         : False,
            'end'           : False,
        }

        options, args = self.parser.parse_args()

        config_file = os.path.abspath(os.environ['HOME'] + "/.xmax.config")
        if not os.path.isfile(config_file):
            config_file = ""

        if options.config_file:
            config_file = options.config_file

        if config_file != "" and not os.path.isfile(config_file):
            print "xmax launch script config file '%s' not found"
            sys.exit(1)

        config = {}
        if config_file != "":
            try:
                config = Config.parse(config_file)
            except Config.ConfigException, ex:
                print "error parsing config file:", str(ex)
                sys.exit(1)

        xmax_dir = asl.xmax_path
        if config.has_key("xmax-dir"):
            xmax_dir = os.path.abspath(config["xmax-dir"])
        if not os.path.isdir(xmax_dir):
            print "xmax directory '%s' could not be located" % xmax_dir
            sys.exit(1)

        xmax_data = os.path.abspath(xmax_dir + "/DATA")
        if config.has_key("xmax-data"):
            xmax_data = os.path.abspath(config["xmax-data"])
        if not os.path.isdir(xmax_dir):
            print "xmax data directory '%s' could not be located" % xmax_data
            sys.exit(1)

        jvm_mem_start = "512M"
        if config.has_key("jvm-mem-start"):
            jvm_mem_start = config["jvm-mem-start"]

        jvm_mem_max = "2048M"
        if config.has_key("jvm-mem-max"):
            jvm_mem_max = config["jvm-mem-max"]

        if options.dump_temp_data:
            xmax_options["dump"] = True

        if options.use_temp_data:
            xmax_options["temp"] = True

        if options.join:
            xmax_options["display"] = '4'
            xmax_options["unit"] = '4'

        if options.network:
            xmax_options["network"] = options.network
        if options.station:
            xmax_options["station"] = options.station
        if options.location:
            xmax_options["location"] = options.location
        if options.channel:
            xmax_options["channel"] = options.channel

        if (len(args) < 1) and (not options.use_temp_data):
            self.usage("No files specified")

        # Expand the file list
        all_files = {}
        for arg in args:
            files = glob.glob(arg)
            for file in files:
                if os.path.isdir(file): 
                    if not options.include_directories:
                        continue
                elif os.path.islink(file):
                    if not options.include_symlinks:
                        continue
                elif not os.path.isfile(file):
                    continue
                full_path = os.path.abspath(file)
                all_files[full_path] = full_path

        # If many files were specified, verify the uses wishes to continue
        if len(all_files) > 128:
            confirm = 'M'
            first = True
            while confirm.lower() not in ('y','n'):
                if not first:
                    print "Please enter 'y' or 'n'"
                first = False
                confirm = raw_input("%d files selected! Are you sure you want to proceed [y/N]?: ")
                if confirm == "":
                    confirm = "n"
            if confirm.lower() != 'y':
                print "Exiting at your request."
                sys.exit(1);

        # If no sources, bail
        if (len(all_files) < 1) and (not options.use_temp_data):
            print "No files match your request."
            sys.exit(1)

        # Remove symlinks from the previous session
        for file in os.listdir(xmax_data):
            if file == '.keep':
                continue
            data_link = os.path.abspath(xmax_data + "/" + file)
            if not os.path.islink(data_link):
                print "non-symlink '%s' found in xmax data directory will not be removed" % data_link
                sys.exit(1)
            os.remove(data_link)

        # Add new symlinks (if any)
        for file_path in all_files.keys():
            link_name = "_".join(file_path.split("/"))
            link_path = os.path.abspath(xmax_data + "/" + link_name)
            try:
                os.symlink(file_path, link_path)
                print "Adding file", file_path
            except Exception, ex:
                print "symlink creation failed:"
                print "  %s -> %s" % (link_path, file_path)
                print "  exception: %s" % str(ex)
                sys.exit(1)

        # Fix for temporary data dump
        if options.dump_temp_data:
            xmax_options["data"] = xmax_data

        # Generate the XMAX options
        option_list = []
        for opt,val in xmax_options.items():
            if val == False:
                continue
            switch = xmax_switches[opt]

            if switch[1] == True:
                option_list.append("%s %s" % (switch[0], val))
            else:
                option_list.append("%s" % switch[0])

        # We don't give a non-gui option since an X server must be running
        # in order to see the XMAX window
        executable = '/bin/bash'
        arguments  = [executable, '-c', "\". ~/.bash_profile; . ~/.bashrc; cd %s; java -version; java -Xms%s -Xmx%s -jar xmax.jar %s\"" % (xmax_dir, jvm_mem_start, jvm_mem_max, ' '.join(option_list))]
        print "Command:", ' '.join(arguments)
        os.popen(' '.join(arguments))

if __name__ == '__main__':
    Main().start()

