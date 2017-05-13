import hashlib
import struct
import logging
import hmac

import pyaes


def get_aes(  # creates an aes object with iv that matches block_num
    key,
    ivkey,
    block_num=None,
):
    # hash key and ivkey to match aes length
    sha = hashlib.sha1()
    sha.update(key)
    key = sha.digest()[:16]

    sha = hashlib.sha1()
    sha.update(ivkey)
    sha.update(str(block_num))
    iv = sha.digest()[:16]

    return pyaes.AESModeOfOperationCBC(key, iv=iv)


def encrypt_block_aes(
    aes,
    block,
):
    index = 0
    result = bytearray(len(block))
    while index < len(block):
        result[index:index + 16] = struct.pack(
            "16s",
            aes.encrypt(
                struct.unpack(
                    "16s",
                    block[index:index + 16]
                )[0]
            )
        )
        index += 16
    return result


def decrypt_block_aes(
    aes,
    block,
):
    index = 0
    result = bytearray(len(block))
    while index < len(block):
        result[index:index + 16] = struct.pack(
            "16s",
            aes.decrypt(
                struct.unpack(
                    "16s",
                    block[index:index + 16],
                )[0]
            )
        )
        index += 16
    return result


def sha(data, *more_data):
    h = hmac.new(data, digestmod=hashlib.sha1)
    for i in more_data:
        h.update(i)
    return h.digest()


def aes_encrypt(
    key,
    iv,
    data,
):
    aes = pyaes.Encrypter(pyaes.AESModeOfOperationCBC(key, iv))
    result = ""
    result += aes.feed(data)
    result += aes.feed()
    return result


def aes_decrypt(
    key,
    iv,
    data,
):
    aes = pyaes.Decrypter(pyaes.AESModeOfOperationCBC(key, iv))
    result = ""
    result += aes.feed(data)
    result += aes.feed()
    return result
