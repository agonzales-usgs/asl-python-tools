import os

mode_map = {
    'r' : os.R_OK,
    'w' : os.W_OK,
    'x' : os.X_OK,
}

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

def test_dir(dir, mode):
    if mode.lower() not in ('r', 'w', 'x'):
        raise Exception("Invalid mode for test_dir()")
    test = mode_map[mode.lower()]
    return os.path.isdir(dir) and os.access(dir, test)

def test_file(file, mode):
    if mode.lower() not in ('r', 'w', 'x'):
        raise Exception("Invalid mode for test_file()")
    test = mode_map[mode.lower()]
    return os.path.isfile(file) and os.access(file, test)

