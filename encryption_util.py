import constants
import hashlib
import struct
import logging

import pyaes

def get_aes( # creates an aes object with iv that matches block_num
    key,
    ivkey,
    block_num,
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
    if len(block) != constants.BLOCK_SIZE:
        raise RuntimeError('encryption data length must be block size')
    result = bytearray(constants.BLOCK_SIZE)
    while index < len(block):
        result[index:index+16] = struct.pack(
            "16s",
            aes.encrypt(
                struct.unpack(
                    "16s",
                    block[index:index+16]
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
    if len(block) != constants.BLOCK_SIZE:
        raise RuntimeError('encryption data length must be block size')
    result = bytearray(constants.BLOCK_SIZE)
    while index < len(block):
        result[index:index+16] = struct.pack(
            "16s",
            aes.decrypt(
                struct.unpack(
                    "16s",
                    block[index:index+16],
                )[0]
            )
        )
        index += 16
    return result
