#!/usr/bin/env python
import clean
import os
import sys
import tarfile
import zipfile

install_script   = 'install.py'
source_dir       = 'asl_utilities'
readme_file      = 'README.txt'
example_dir      = 'examples'
archive_name     = 'asl_utilities'
tar_compression  = 'bz2'
tar_prefix       = 'asl_utilities/'

tar_archive      = '%s.tar.%s' % (archive_name, tar_compression)
zip_archive      = '%s.zip' % archive_name

def package():
    if not os.path.exists(source_dir):
        print "%s directory does not exist" % source_dir
        sys.exit(1)
    elif not os.path.isdir(source_dir):
        print "%s exists, but it is not a directory" % source_dir
        sys.exit(1)

    print "Cleaning directory %s ..." % source_dir
    clean.clean_dir(source_dir)

    if os.path.exists(zip_archive):
        print "Deleting old package %s ..." % zip_archive
        os.remove(zip_archive)

    if os.path.exists(tar_archive):
        print "Deleting old package %s ..." % tar_archive
        os.remove(tar_archive)

    print "Packaging files ..."

    print "    creating package %s ..." % zip_archive
    factory = zipfile.ZipFile(zip_archive, 'w', zipfile.ZIP_DEFLATED)
    zip_write(factory, source_dir)
    zip_write(factory, example_dir)
    zip_write(factory, install_script)
    zip_write(factory, readme_file)
    factory.close()

    print "    creating package %s ..." % tar_archive
    factory = tarfile.open(tar_archive, 'w:%s' % tar_compression)
    factory.add(example_dir,    '%s%s' % (tar_prefix, example_dir))
    factory.add(source_dir,     '%s%s' % (tar_prefix, source_dir))
    factory.add(install_script, '%s%s' % (tar_prefix, install_script))
    factory.add(readme_file,    '%s%s' % (tar_prefix, readme_file))
    factory.close()

def zip_write(factory, path):
    if os.path.isdir(path):
        for f in os.listdir(path):
            zip_write(factory, path + '/' + f)
    else:
        factory.write(path)

if __name__ == '__main__':
    package()
