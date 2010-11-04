#!/usr/bin/env python
import os
import shutil
import sys

mode_map = {
    'INSTALL' : {
        'bin'   : 'copy',
        'lib'   : 'copy',
        'icons' : 'copy',
        'utils' : 'copy',
    },
    'UPGRADE' : {
        'bin'   : 'replace',
        'lib'   : 'replace',
        'icons' : 'replace',
        'utils' : 'update',
    },
}

def copy(src, dst):
    print "Copying: %s -> %s" % (src, dst) 
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst, symlinks=True)

def replace(src, dst):
    print "Replacing: %s -> %s" % (src, dst) 
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst, symlinks=True)

def update(src, dst):
    print "Updating: %s -> %s" % (src, dst) 
    if not os.path.exists(dst):
        if os.path.isfile(src):
            shutil.copy(src, dst)
        else:
            shutil.copytree(src, dst)
    elif os.path.isfile(dst):
        os.remove(dst)
        shutil.copy(src, dst)
    elif os.path.isdir(src):
        for file in os.listdir(src):
            update(os.path.abspath(src+'/'+file), os.path.abspath(dst+'/'+file))

def sink(src, dst):
    print "No action taken for %s -> %s" % (src, dst)

def install(src, dst, mode):
    func = sink
    for path,method in mode_map[mode].items():
        if method == 'copy':
            func = copy
        elif method == 'replace':
            func = replace
        elif method == 'update':
            func = update
        func(os.path.abspath("%s/%s" % (src, path)), os.path.abspath("%s/%s" % (dst, path)))

def main():
    mode = 'INSTALL'
    this_path = os.path.abspath('.')
    src_path  = os.path.abspath('./asl_utilities')
    print "This path", this_path
    print "Source path", src_path

    if not os.path.exists(src_path):
        print "Could not find asl_utilities directory"
        sys.exit(1)
    try:
        home_path = os.environ['HOME']
    except:
        home_path = os.environ['USERPROFILE']

    path_file = home_path + '/.asl_utilities_path'

    if os.path.exists(path_file):
        fh = open(path_file, 'r')
        install_path = fh.readline().strip()
        fh.close()
        if os.path.isdir(install_path):
            response = 'C'
            while response.upper() not in ('U','I','Q'):
                response = raw_input("asl_utilities appears to be installed, do you wish to upgrade[u], install elsewhere[i] or quit[q]: ")
            if response.upper() == 'I':
                mode = 'INSTALL'
            elif response.upper() == 'U':
                mode = 'UPGRADE'
            else:
                sys.exit(0)


    if mode == 'INSTALL':
        default_path = os.path.abspath(home_path + '/asl_utilities')
        install_path = raw_input("Where would you like to install [%s]: " % default_path)
        install_path = os.path.abspath(install_path)
        if install_path == '':
            install_path = default_path
        if (install_path == src_path) or (install_path == this_path):
            print "You cannot install to the source directory."
            print "Please either move the source directory, or select another install location."
            sys.exit(1)
        if os.path.isdir(install_path):
            response = 'C'
            while response.upper() not in ('Y','N',''):
                response = raw_input("Directory %s already exists, do you wish to install anyway (y/N): " % install_path)
            if response.upper() != 'Y':
                sys.exit(0)
            mode = 'UPGRADE'
        elif os.path.exists(install_path):
            print "%s exists, but it is not a directory" % install_path
            sys.exit(1)
        else:
            try:
                os.mkdir(install_path)
            except:
                print "could not create install directory %s" % install_path
                sys.exit(1)
        fh = open(path_file, 'w+')
        fh.write(install_path + '\n')
        fh.close()

    print "Calling install with mode", mode
    install(src_path, install_path, mode)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass

