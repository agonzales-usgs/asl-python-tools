#!/usr/bin/python
import os
import shutil
import sys
import traceback

if __name__ == "__main__":
    try:
        try:
            home = os.environ["HOME"]
        except KeyError:
            home = os.environ["USERPROFILE"]
        print home

        asl_utilities_path = os.path.abspath("./asl_utilities")

        path_file_name = ".asl_utilities_path"
        path_file = os.path.abspath("%s/%s" % (home, path_file_name))

        print "Writing path file '%s'" % path_file
        print "    Contents: %s" % asl_utilities_path

        fh = open(path_file, "w+")
        fh.write("%s\n" % asl_utilities_path)
        fh.close()

    except Exception, ex:
        print "[Exception]>", str(ex)
        (ex_f, ex_s, trace) = sys.exc_info()
        traceback.print_tb(trace)

    print

    raw_input("Press ENTER/RETURN key to Exit")

