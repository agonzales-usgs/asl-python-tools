import hashlib

__engines = {
    'MD5'     : hashlib.md5,
    'SHA-1'   : hashlib.sha1,
    'SHA-224' : hashlib.sha224,
    'SHA-256' : hashlib.sha256,
    'SHA-384' : hashlib.sha384,
    'SHA-512' : hashlib.sha512,
}

def __get_engine(key):
    engine = None
    if __engines.has_key(key):
        engine = __engines[key]()
    return engine

def get_engine_list():
    return __engines.keys()

def sum(filename, key):
    engine = __get_engine(key)
    digest = ''
    if engine is not None:
        with open(filename,'rb') as f:
            for chunk in iter(lambda: f.read(engine.block_size), ''):
                engine.update(chunk)
        digest = engine.hexdigest()
    return digest

