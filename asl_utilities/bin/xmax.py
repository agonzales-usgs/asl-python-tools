#!/usr/bin/evn python
import asl

import glob     # for matching file patterns
import optparse # argument parsing
import os
import signal
import sys

from jtk import Config # generic key=value config file support

class Main:
    def __init__(self):
        signal.signal(signal.SIGTERM, self.halt_now)
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
            "-s", "--include-symlinks", 
            dest="include_symlinks", 
            action="store_true", 
            help="Symlinks should be created to matched symlinks"))
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
        options, args = self.parser.parse_args()

        config_file = os.path.abspath(os.environ['HOME'] + "/.xmax.config")
        if not os.path.isfile(config_file):
            config_file = ""

        if options.config_file:
            config_file = options.config_file

        if config_file != "" and not os.path.isfile(config_file):
            print "xmax launch script config file '%s' not found"
            sys.exit(1)

        try:
            config = Config.parse(config_file)
        except ConfigException, ex:
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

        if len(args) < 1:
            self.usage("No files specified")

        all_files = {}
        for arg in args:
            files = glob.glob(args)
            for file in files:
                if os.path.isdir(file): 
                    if not options.include_directories:
                        continue
                elif os.path.islink(file):
                    if not options.include_symlinks:
                        continue
                elif not os.path.isfile(file)
                    continue
                full_path = os.path.abspath(file)
                all_files[full_path] = full_path

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

        if len(all_files) < 1:
            print "No files match your request."
            sys.exit(1)

        for file in os.listdir(xmax_data):
            data_link = os.path.abspath(xmax_data + "/" + file
            if not os.path.islink(data_link):
                print "non-symlink found int xmax data directory: '%s'" % data_link
            os.remove(data_link)

        for file_path in all_files.keys():
            link_name = "_".join(file_path.split("/"))
            link_path = os.path.abspath(xmax_data + "/" + link_name)
            try:
                os.link(file_path, link_path)
            except Exception, ex:
                print "symlink creation failed:"
                print "  %s -> %s" % (link_path, file_path)
                print "  exception: %s" % str(ex)

        #executable = '/usr/bin/xterm'
        #arguments  = ['xterm', '-T', '\"XMAX\"', '-sl', '10240', '-e', "\". ~/.bash_profile; . ~/.bashrc; cd %s; java -version; java -Xms1024M -Xmx1024M -jar xmax.jar %s && read -n 1 -p 'Press any key to continue...'\"" % (self.xmax_directory, ' '.join(option_list))]
        #print "Command:", ' '.join(arguments)
        #os.popen(' '.join(arguments))
        #return None

        #process = subprocess.Popen(arguments)
        #return process

if __name__ == '__main__':
    Main().start()

