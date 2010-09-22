#!/usr/bin/env python
import glob
import os
import shlex
import subprocess
import sys

cmds = {
    'help' : {
        'description' : "Display this help dialog",
    },
    'cp' : {
        'description' : "Copy (duplicate) files",
    },
    'mv' : {
        'description' : "Rename (move) files",
    },
    'rm' : {
        'description' : "Remove (delete) files",
    },
    'ln' : {
        'description' : "Link files to other locations",
    },
    'ls' : {
        'description' : "Display file/directory listing",
    },
    'pwd' : {
        'description' : "Print the working directory",
    },
    'cd' : {
        'description' : "Change working directory",
    },
}

def loop():
    running = True
    line = ''
    prompt = '> '
    home = os.path.abspath('.')
    if os.environ.has_key('HOME'):
        home = os.path.abspath(os.environ['HOME'])
    while running:
        try:
            line = raw_input(prompt)
            args = shlex.split(line)
            line = ''
            if len(args) == 0:
                continue
            elif args[0] == 'help':
                for k in sorted(cmds.keys()):
                    print k, "-", cmds[k]['description']
                continue
            elif args[0] == 'cd':
                if len(args) < 2:
                    os.chdir(home)
                    continue
                target = os.path.abspath(args[1])
                if not os.path.exists(target):
                    print "%s: no such file or directory" % target
                    continue
                if not os.path.isdir(target):
                    print "%s: no such file or directory" % target
                    continue
                print target
                os.chdir(target)
                continue
            elif args[0] == 'pwd':
                print os.getcwd()
                continue
            elif not cmds.has_key(args[0]):
                print "Invalid command '%s'. Type 'help' for a list of commands." % args[0]
                continue
            proc = subprocess.Popen(args) #, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            proc.wait()
        except KeyboardInterrupt:
            print
            continue
        except EOFError:
            print
            break
            

def main():
    loop()

if __name__ == '__main__':
    main()

