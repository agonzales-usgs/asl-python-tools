import os

def scan_directories(dir_list, depth=1):
    files = []
    for dir in dir_list:
        files.extend(scan_directory(dir, depth))
    return files

def scan_directory(directory, depth=1):
    files = []
    if os.path.islink(directory):
        pass
    elif os.path.isdir(directory):
        if depth:
            for name in os.listdir(directory):
                files.extend(scan_directory(os.path.abspath("%s/%s" % (directory, name)), depth - 1))
    elif os.path.isfile(directory):
        files = [directory]
    return files

def dir_from_file_path(file):
    dir = ""
    dir_parts = file.rsplit("/", 1)
    if len(dir_parts) != 2:
        dir_parts = file.rsplit("\\", 1)
    if len(dir_parts):
        dir = dir_parts[0]
    return dir

