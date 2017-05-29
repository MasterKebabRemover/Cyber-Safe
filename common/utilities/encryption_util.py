## @package common.utilities.encryption_util
#
# Various encryption related utilities.
## @file encryption_util.py Implementation of @ref common.utilities.encryption_util
import base64
import hashlib
import struct
import logging
import hmac

import pyaes

## Create AES encryption object
# @param key (str) encryption key.
# @param ivkey (str) encryption iv generation key.
# @param block_num (int) block number for iv generation.
# @returns (pyaes.AESModeOfOperationCBC) encryption object.
#
# uses external pyaes module to generate an AES encryption object.
# object encryption key is given as parameter.
# object initial vector generated from given iv_key and depends on current block number.
#
def get_aes(
    key,
    ivkey,
    block_num=None,
):
    sha = hashlib.sha1()
    sha.update(key)
    key = sha.digest()[:16]

    sha = hashlib.sha1()
    sha.update(ivkey)
    sha.update(str(block_num))
    iv = sha.digest()[:16]

    return pyaes.AESModeOfOperationCBC(key, iv=iv)

## Encrypt block using AES.
# @param aes (pyaes.AESModeOfOperationCBC) encryption object.
# @param block (str) block to encrypt.
# @returns (str) encrypted block.

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

## Decrypt block using AES.
# @param aes (pyaes.AESModeOfOperationCBC) encryption object.
# @param block (str) block to encrypt.
# @returns (str) decrypted block.
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

## Sha1 hash algorithm.
# @param data (str) data to digest
# @param *more_data (list) more data to digest.
# @returns (str) sha1 digested data.
def sha(data, *more_data):
    h = hmac.new(data, digestmod=hashlib.sha1)
    for i in more_data:
        h.update(i)
    return h.digest()

##  AES encryption.
# @param key (str) encryption key.
# @param iv (str) encryption iv.
# @param data (str) data to encrypt.
# @returns (str) data encrypted by AES key and iv.
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

##  AES decryption.
# @param key (str) decryption key.
# @param iv (str) decryption iv.
# @param data (str) data to decrypt.
# @returns (str) data decrypted by AES key and iv.
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

## Basic authentication check.
# @param request_context (dict) request context.
# @returns (bool) whether authentication was successful.
#
# checks request_context for authentication header, compares received user and password to 
# hash of user and password from self config file.
#
def check_login(request_context):
    successful_login = False
    if "Authorization" in request_context["req_headers"].keys():
        auth_type, auth_content = request_context["req_headers"][
            "Authorization"
        ].split(" ", 2)
        if auth_type == "Basic":
            username, password = tuple(base64.b64decode(auth_content).split(':', 1))
            config = request_context["app_context"]["config"]
            salt = base64.b64decode(config.get('blockdevice', 'salt'))
            successful_login = (
                sha(username, salt) == base64.b64decode(config.get('blockdevice', 'username_hash')) and
                sha(password, salt) == base64.b64decode(config.get('blockdevice', 'password_hash'))
            )
    return successful_login
