#!/usr/bin/python
try:
    import base64
    import getpass  # to get user's password
    import optparse # command line argument parsing
    import os
    import platform
    import pty      # bypass pexpect when it can't help us
    import re       # regular expressions for password verification
    import select   # wait (select) on file descriptors
    import struct
    import subprocess
    import sys
    import time

    import pexpect  # expect lib
    from Logger import Logger
except Exception, e:
    print "Exception: " + e.__str__()
    import time
    time.sleep(3)
    raise Exception, "crypt could not be initialized. Exception: " + e.__str__()

try:
    import hashlib
    sha1 = hashlib.sha1
except:
    import sha
    sha1 = sha.new

ENCRYPT = False
DECRYPT = True

SD_NEITHER   = 0
SD_FROM_FILE = 1
SD_TO_FILE   = 2
SD_BOTH      = 3

class Crypt:
    def __init__(self):
        self.mode = ENCRYPT
        self.shell     = "/bin/bash -c"

        self.password = ""
        self.seed     = ""
        self.action   = ""

        self.in_file  = ""
        self.out_file = ""
        self.read_timeout = 1

        self.logger = Logger()
        self.logger.set_log_note("Crypt")
        self.logger.set_log_to_file(False)

        try:
            home_directory = os.path.abspath(os.environ['HOME'])
        except:
            home_directory = os.path.abspath(os.environ['USERPROFILE'])
        asl_path_file = os.path.abspath(home_directory + '/.asl_utilities_path')
        if not os.path.isfile(asl_path_file):
            raise Exception("Crypt: Could not locate ASL Utilities directory")
        fh = open(asl_path_file, 'r')
        path = fh.readline().strip()
        if not os.path.exists(path):
            raise Exception("ASL Utilities directory '%s' does not exist" % path)
        if not os.path.isdir(path):
            raise Exception("path '%s' exists, but is not a directory" % path)

        if platform.system() == 'Linux':
            self.executable = os.path.abspath(path + '/utils/aescrypt/aescrypt.linux')
        elif platform.system() == 'FreeBSD':
            self.executable = os.path.abspath(path + '/utils/aescrypt/aescrypt.bsd')
        else:
            self.executable = os.path.abspath(path + '/utils/aescrypt/aescrypt.exe')
        if not os.path.exists(self.executable):
            raise Exception("Unable to locate aescrypt executable")

    def build_actions(self):
        self.action = self.shell + " \"%s" % self.executable
        if self.mode == DECRYPT:
            self.action += " -d"
        else:
            self.action += " -e"
        self.action += " -o " + self.out_file
        self.action += " " + self.in_file
        self.action += "\""

    def _log(self, str, category="info"):
        if category == "":
            self.logger.log( str )
        else:
            self.logger.log( str, category )

    def log_file_name(self, name=""):
        self.logger.set_file( name )
        return self.logger.get_file()

    def log_to_file(self, to_file=True):
        self.logger.set_log_to_file( to_file )

    def log_to_screen(self, to_screen=True):
        self.logger.set_log_to_screen( to_screen )


    def run(self):
        self.build_actions()
        try:
            reader = pexpect.spawn( self.action )
            reader.expect( "Enter password:" )
            reader.sendline( self.password )
            if self.mode == ENCRYPT:
                reader.expect( "Re-Enter password:" )
                reader.sendline( self.password )
            reader.expect( pexpect.EOF )
        except Exception, e:
            self._log( "Caught Exception: " + e.__str__() )
            return 0
        return 1

    def crypt_data(self, data_unprocessed='', src_file=None, dst_file=None):
        data_processed = ""
        page_size      = 512

        src_dst = SD_NEITHER
        if src_file is not None:
            src_dst |= SD_FROM_FILE
        if dst_file is not None:
            src_dst |= SD_TO_FILE

        arg_list = [self.executable]
        arg_list.append("-k")
        arg_list.append("-")
        # direction
        if self.mode == DECRYPT:
            arg_list.append("-d")
        else:
            arg_list.append("-e")
        # output
        arg_list.append("-o")
        if src_dst & SD_TO_FILE:
            arg_list.append(dst_file)
        else:
            arg_list.append("-")
        # input
        if src_dst & SD_FROM_FILE:
            arg_list.append(src_file)
        else:
            arg_list.append("-")

        #print "Command:", ' '.join(arg_list)

        child = subprocess.Popen(arg_list, 0, self.executable, subprocess.PIPE, subprocess.PIPE, subprocess.PIPE)

        aes_stdin = child.stdin.fileno()
        aes_stdout = child.stdout.fileno()
        aes_stderr = child.stderr.fileno()

        try:
            # Write the key to the child
            try:
                key_s_read  = []
                key_s_write = [aes_stdin]
                key_s_error = []
                digest = sha1(self.password).digest() + sha1(self.password[::-1]).digest()[0:12]
                key = struct.pack("!H", len(digest)) + digest
                #print "key:", base64.standard_b64encode(key)

                total = len(key)
                count = 0
                index = 0
                #self._log("Sending key [%s] of length %d to child..." % (base64.standard_b64encode(key), len(key)))
                while True:
                    buffer = key[index:]
                    #self._log("selecting on file descriptors...")
                    (readable, writeable, errors) = select.select( key_s_read, key_s_write, key_s_error )
                    #self._log("file descriptor(s) ready.")
                    if errors:
                        for error_fd in errors:
                            info = os.read(error_fd, page_size)
                            self._log("Got error from fd %d: %s" % (error_fd, info))
                        raise Exception, "child process had an error."
                    if aes_stdin in writeable:
                        try:
                            bytes = os.write(aes_stdin, buffer)
                            #bytes = child.stdin.write(buffer)
                            #child.stdin.flush()
                        except OSError, e:
                            self._log("Key pipe broken.")
                            break
                        self._log("Key sent.")
                        count += bytes
                        index += bytes
                        if count >= total:
                            break
            except IOError, e:
                raise Exception, "aes_stdin: pipe broken."

            if src_dst == SD_BOTH:
                # If the child process is handling its own I/O
                # just wait for it to finish.
                self._log("Waiting on child process")
                child.wait()
            else:
                # We do writes and reads simultaneously because we
                # don't know how large the data is going to be. If
                # we simply wrote everything first, then started
                # reading, we run the risk of filling up the pipe.
                try:
                    aes_s_read  = [aes_stderr]
                    aes_s_write = []
                    aes_s_error = []
                    total = len( data_unprocessed )
                    bytes = 0
                    count = 0
                    index = 0
                    write_done = False
                    read_done  = False
                    error_done = False

                    if src_dst & SD_FROM_FILE:
                        write_done = True
                    else:
                        aes_s_write.append(aes_stdin)

                    if src_dst & SD_TO_FILE:
                        read_done = True
                    else:
                        aes_s_read.append(aes_stdout)

                    self._log( "Starting communication with child." )
                    while True:
                        buffer = data_unprocessed[index:]
                        (readable, writeable, errors) = select.select( aes_s_read, aes_s_write, aes_s_error )
                        if errors:
                            for error_fd in errors:
                                info = os.read( error_fd, page_size )
                                self._log("Got error from fd %d: %s" % (error_fd, info), "error")
                            raise Exception, "child process had an error"
                        if (aes_stdin in writeable) and (not write_done):
                            self._log( "Child's stdin is ready for data." )
                            try:
                                bytes = os.write( aes_stdin, buffer )
                            except OSError, e:
                                self._log( "Child's stdin pipe is broken." )
                                issues = os.read( aes_stderr, page_size )
                                self._log( "Error message from child: %s" % issues )
                                break
                            self._log( "Data block sent to child." )
                            count += bytes
                            index += bytes
                            if count >= total:
                                write_done = True
                                if aes_s_write.count( aes_stdin ):
                                    aes_s_write.remove( aes_stdin )
                                if aes_s_error.count( aes_stdin ):
                                    aes_s_error.remove( aes_stdin )
                                #os.close( aes_stdin )
                                child.stdin.close()
                                self._log( "All data has been sent." )
                        if aes_stdout in readable:
                            self._log( "Child's stdout has data buffered." )
                            try:
                                temp = os.read( aes_stdout, page_size )
                            except OSError, e:
                                self._log( "Child's stdout pipe is broken" )
                                break
                            if (not temp) and write_done:
                                if not read_done:
                                    self._log( "Received first empty string from child's stdout." )
                                    read_done = True
                                else:
                                    self._log( "Received second empty string from child's stdout." )
                                    break
                            else:
                                self._log( "Data block received from child. %d bytes." % len(temp) )
                                read_done = False
                                data_processed += temp
                        if aes_stderr in readable:
                            self._log( "child's stderr has data buffered" )
                            try:
                                temp = os.read( aes_stderr, page_size )
                            except OSError, e:
                                self._log( "child pipe broken > stderr" )
                                break
                            if (not temp) and write_done:
                                if not error_done:
                                    self._log( "Received empty string from child's stderr. Ignoring." )
                                    #self._log( "received first blank > stderr" )
                                    #error_done = True
                                #else:
                                #    self._log( "received second blank > stderr" )
                                    #break
                            else:
                                self._log( "Message from child's stderr: %s" % temp )
                                #error_done = False
                        if (src_dst & SD_TO_FILE) and write_done:
                            self._log( "Child is handling output and we are done writing." )
                            break
                except IOError, e:
                    raise Exception, "pipe broken"

        #except Exception, e:
        except IOError, e:
            self._log("caught exception: %s\n" % str(e), cat="err")

        return data_processed

    def get_password(self, once=1):
        msg = "No password entered..."
        while 1:
            passwordV = ""
            password = getpass.getpass( "Password: " )
            if not once:
                passwordV = getpass.getpass( "Verify Password: " )
            if (once) or (password == passwordV):
                msg = self.set_password( password )
                if msg == "":
                    break
                else:
                    print msg
            else:
                print "Passwords did not match. Try again."
        return msg

    def set_password(self, password):
        require1 = re.compile('.{8,}')
        require2 = re.compile('[a-z]')
        require3 = re.compile('[A-Z]')
        require4 = re.compile('[0-9]')

        if not require1.search( password, 0 ):
            return "Password must be at least 8 characters long."
        if not require2.search( password, 0 ):
            return "Password must contain at least one lower case letter."
        if not require3.search( password, 0 ):
            return "Password must contain at least one upper case letter."
        if not require4.search( password, 0 ):
            return "Password must contain at least one numeric character."

        self.password = password
        return ""
        
    def set_input(self, filename):
        self.in_file = filename

    def set_output(self, filename):
        self.out_file = filename

    def set_mode(self, direction):
        self.mode = direction


def usage():
    print "usage: encrypt.py [-h] [-d] -i|--input=infile -o|--output=outfile"

def main():
    option_list = [
        optparse.make_option("-d", "--decrypt", action="store_true", dest="decrypt", help="decrypt instead of encrypting"),
        optparse.make_option("-i", "--input-file", type="string", action="store", dest="input_file", help="which form which input will be read"),
        optparse.make_option("-o", "--output-file", type="string", action="store", dest="output_file", help="file to which output will be written"),
        optparse.make_option("-v", action="count", dest="verbosity", help="verbosity (multiple times to increase verbosity)"),
    ]

    parser = optparse.OptionParser(option_list=option_list)
    options, args = parser.parse_args()

    verbosity = 0
    in_file = ""
    out_file = ""
    decrypt = 0

    if options.verbosity:   verbosity = options.verbosity
    if options.input_file:  in_file   = options.input_file
    if options.output_file: out_file  = options.output_file
    if options.decrypt:     decrypt   = options.decrypt

    try:
        # get input file
        if decrypt:
            in_prompt = "File to decrypt: "
        else:
            in_prompt = "File to encrypt: "

        if (in_file == ""):
            in_file = raw_input(in_prompt)
        if in_file == "":
            print "Must specify an input file"
            exit(1)

        # get output file
        out_prompt = "File to save to"
        default_out_file = ""
        if decrypt:
            if (len(in_file) > 4) and (in_file[-4:] == ".aes"):
                default_out_file = in_file[:-4]
        else:
            default_out_file = in_file + ".aes"

        if default_out_file != "":
            out_prompt += "\n[" + default_out_file + "]: "
        else:
            out_prompt += ": "

        if out_file == "":
            out_file = raw_input(out_prompt)
        if out_file == "":
            if default_out_file == "":
                print "Must specify an output file"
            else:
                out_file = default_out_file

        engine = Crypt()
        args  = sys.argv[1:]

        #engine.log_file_name("engine.log")
        #engine.log_to_file()
        engine.log_to_screen()
        engine.set_mode(decrypt)
        message = engine.get_password(once=decrypt)
        if message != "":
            print message
            sys.exit(1)
        engine.crypt_data(src_file=in_file, dst_file=out_file)
    except KeyboardInterrupt:
        print ""
        sys.exit(0)
    except SystemExit:
        print ""
        sys.exit(0)
    except EOFError:
        print ""
        sys.exit(0)

if __name__ == "__main__":
    main()

