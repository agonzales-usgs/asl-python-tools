#!/usr/bin/env python
# Support for the AESCrypt file format

class AESInvalidFileFormat(Exception):
    """Invalid file format"""

class AESBadVersion(Exception):
    """Unsupported file format version"""

DEFAULT_VERSION = 2

versions = {
    0 : AESVersion0,
    1 : AESVersion1,
    2 : AESVersion2,
}

class AESCrypt:
    def read_file(self, file):
        fh = open(file, "rb")
        if fh.read(3) != "AES":
            raise 
        if versions.has_key(struct.unpack(">B", fh.read(1))[0])

    def write_file(self, file, content, version=DEFAULT_VERSION):
        wh = open(file, "wb+")

class AESVersion:
    def __init__(self):
        self.type    = "AES"
        self.version = -1

    def decompose(self):
        self._decompose()

    def _decompose(self):
        raise NotImplementedError("'_decompose' method must be overridden by the child class")

    def compose(self):
        self._compose()

    def _compose(self):
        raise NotImplementedError("'_compose' method must be overridden by the child class")


class AESVersion0(AESVersion):
    def __init__(self):
        AESVersion.__init__(self)
        self.version = 0
        self.pad_length = None
        self.IV = None
        self.cipher_text = None
        self.HMAC = None

    def _decompose(self):
        pass

    def _compose(self):
        pass
        


class AESVersion1(AESVersion):
    def __init__(self):
        AESVersion.__init__(self)
        self.version = 1
        self.reserved = 0
        self.IV = None
        self.encrypted_IV_and_key = None
        self.HMAC = None
        self.cipher_text = None
        self.pad_length = -1
        self.HMAC = None

    def _decompose(self):
        pass

    def _compose(self):
        pass
        

class AESVersion2(AESVersion):
    def __init__(self):
        AESVersion.__init__(self)
        self.version = 2
        self.reserved = 0
        self.extensions = []
        self.IV = None
        self.encrypted_IV_and_key = None
        self.HMAC = None
        self.cipher_text = None
        self.pad_length = -1
        self.HMAC = None

    def _decompose(self):
        pass

    def _compose(self):
        pass
        

