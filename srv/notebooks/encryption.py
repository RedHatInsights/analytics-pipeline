import base64
import hashlib
import logging
import os
from decimal import Decimal
import datetime

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend


__all__ = ['get_encryption_key',
           'encrypt_value',
           'decrypt_value']

logger = logging.getLogger('tower_analytics_report.encryption')

SECRET_KEY = 'foobar'
#if not SECRET_KEY:
#    logger.error('Secret key required!')


class Fernet256(Fernet):
    '''Not techincally Fernet, but uses the base of the Fernet spec and uses AES-256-CBC
    instead of AES-128-CBC. All other functionality remain identical.
    '''
    def __init__(self, key, backend=None):
        if backend is None:
            backend = default_backend()

        key = base64.urlsafe_b64decode(key)
        if len(key) != 64:
            raise ValueError(
                "Fernet key must be 64 url-safe base64-encoded bytes."
            )

        self._signing_key = key[:32]
        self._encryption_key = key[32:]
        self._backend = backend


_PROTECTED_TYPES = (
    type(None), int, float, Decimal, datetime.datetime, datetime.date, datetime.time,
)


def smart_str(s):
    """
    Return a string representing 's'. Treat bytestrings as UTF-8.
    """
    # Handle the common case first for performance reasons.
    if issubclass(type(s), str) or isinstance(s, _PROTECTED_TYPES):
        return s
    if isinstance(s, bytes):
        return str(s, 'utf-8')
    return str(s)


def smart_bytes(s):
    """
    Return a bytestring version of 's', encoded as UTF-8.

    Similar to smart_bytes, except that lazy instances are resolved to
    strings, rather than kept as lazy objects.
    """
    # Handle the common case first for performance reasons.
    if isinstance(s, bytes) or isinstance(s, _PROTECTED_TYPES):
        return s
    if isinstance(s, memoryview):
        return bytes(s)
    return s.encode()


def get_encryption_key(field_name, pk=None, secret_key=None):
    '''
    Generate key for encrypted password based on field name,
    ``SECRET_KEY``, and instance pk (if available).

    :param pk: (optional) the primary key of the model object;
               can be omitted in situations where you're encrypting a setting
               that is not database-persistent (like a read-only setting)
    '''
    h = hashlib.sha512()
    if secret_key is None:
        h.update(smart_bytes(SECRET_KEY))
    else:
        h.update(smart_bytes(secret_key))
    if pk is not None:
        h.update(smart_bytes(str(pk)))
    h.update(smart_bytes(field_name))
    return base64.urlsafe_b64encode(h.digest())


def hash_value(value):
    '''
    Hash a value salted with the SECRET_KEY

    :param value: the value to be hashed
    '''
    h = hashlib.sha512()
    h.update(smart_bytes(SECRET_KEY))
    h.update(smart_bytes(value))
    return base64.urlsafe_b64encode(h.digest())


def encrypt_value(key, value):
    value = smart_str(value)
    f = Fernet256(key)
    encrypted = f.encrypt(smart_bytes(value))
    b64data = smart_str(base64.b64encode(encrypted))
    tokens = ['$encrypted', 'UTF8', 'AESCBC', b64data]
    return '$'.join(tokens)


def decrypt_value(encryption_key, value):
    raw_data = value[len('$encrypted$'):]
    # If the encrypted string contains a UTF8 marker, discard it
    utf8 = raw_data.startswith('UTF8$')
    if utf8:
        raw_data = raw_data[len('UTF8$'):]
    algo, b64data = raw_data.split('$', 1)
    if algo != 'AESCBC':
        raise ValueError('unsupported algorithm: %s' % algo)
    encrypted = base64.b64decode(b64data)
    f = Fernet256(encryption_key)
    value = f.decrypt(encrypted)
    return smart_str(value)


def is_encrypted(value):
    if not isinstance(value, str):
        return False
    return value.startswith('$encrypted$') and len(value) > len('$encrypted$')


def decrypt_field(decrypt, entry, field):
    try:
        entry[field] = decrypt(entry[field])
    except Exception:
        entry[field] = '$encrypted$'
        logger.error("decryption error %s", field)
