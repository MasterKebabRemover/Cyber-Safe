## @package common.root_entry
# Class of handling file entry in directory root block
## @file root_entry.py Implementation of @ref common.root_entry
from common.utilities import encryption_util
import logging
import os
import struct

## Indices of various fields in entry.
# each index is it's field's starting index.
# - allocated: Marks whether entry is empty or allocated.
# - iv_size: Size of initial vector.
# - iv: Initial vector for encryption of file size and name.
# - file_size: File size.
# - file_name_length: Length of file name.
# - file_name: File name.
# - main_block_num: Index of file main block on block device.
# - blank: Bytes left blank for future use.
# - random: A random integer.
# - sha: Sha1 hash of file name and random.
# - end: End index of entry.

INDICES = {
    "allocated": 0, # marks whether entry is empty or not
    "iv_size": 1,
    "iv": 2,
    "file_size": 34,
    "file_name_length": 38,
    "file_name": 39,
    "main_block_num": 226,
    "blank": 230,
    "random": 236,
    "sha": 240,
    "end": 256,
}

## Root entry.
#
# Loads an entry string representation and operates on it cleanly.
#
class RootEntry(object):
    ## Constructor.
    def __init__(self):
        self._entry = bytearray(INDICES["end"])

    ## String representation
    # @returns (str) self bytes.
    def __str__(self):
        return str(self._entry)

    ## Check if entry is empty.
    # @returns (bool) false if full, true if empty.
    def is_empty(self):
        return not self._entry[INDICES["allocated"]]

    ## Loads a new entry.
    # @param entry (str) entry string bytes.
    def load_entry(self, entry):
        if len(entry) != INDICES["end"]:
            raise RuntimeError('Invalid entry')
        self._entry = entry


    ## Check ownership of entry with user key.
    # @param file_name (str) file name.
    # @param user_key (str) user key.
    # @returns (bool) true if file name and user key match to those of the entry.
    def compare_sha(
        self,
        file_name,
        user_key,
    ):
        return encryption_util.sha(
            self.random, user_key, file_name)[
            :16] == self.sha

    ## Update the encrypted part of the entry.
    # @param user_key (str) key of encryption.
    # @param file_size (int) file size to encrypt.
    # @param file_name (str) file name to encrypt.
    # 
    # encrypts using AES and self initial vector.
    #
    def set_encrypted(
        self,
        user_key,
        file_size,
        file_name,
    ):
        if len(file_name) > 64:
            raise RuntimeError('file name too long')
        file_name_length = struct.pack(">B", len(file_name))
        file_size = struct.pack(">I", file_size)
        file_name += os.urandom(  # padding file_name
            175 - len(file_name)
        )
        encrypted = encryption_util.aes_encrypt(
            key=user_key,
            iv=self.iv,
            data=file_size + file_name_length + file_name,
        )
        self._entry[INDICES["file_size"]:INDICES["main_block_num"]] = encrypted

    ## Decrypts self encrypted part with given key.
    # @param user_key (str) decryption key.
    # @return (dict) file size and file name.
    def get_encrypted(
        self,
        user_key,
    ):
        decrypted = encryption_util.aes_decrypt(
            key=user_key,
            iv=self.iv,
            data=str(self._entry[INDICES["file_size"]:INDICES["main_block_num"]])
        )
        file_size = struct.unpack(">I", decrypted[:4])[0]
        file_name_length = struct.unpack(">B", decrypted[4:5])[0]
        file_name = decrypted[5:5 + file_name_length]
        return {
            "file_size": file_size,
            "file_name": file_name,
        }

    ## Mark self as full.
    def mark_full(self):
        self._entry[INDICES["allocated"]: INDICES["iv_size"]] = chr(1)    

    ## Mark self as empty.
    def mark_empty(self):
        self._entry[INDICES["allocated"]: INDICES["iv_size"]] = chr(0)    

    @property
    def iv_size(self):
        return struct.unpack(
            ">B",
            self._entry[INDICES["iv_size"]:INDICES["iv"]],
        )[0]

    @iv_size.setter
    def iv_size(self, value):
        self._entry[INDICES["iv_size"]:INDICES["iv"]] = struct.pack(
            ">B",
            value,
        )

    @property
    def iv(self):
        return str(self._entry[INDICES["iv"]:INDICES["iv"] + self.iv_size])

    @iv.setter
    def iv(self, value):
        if len(value) != self.iv_size:
            raise RuntimeError('iv size does not match varibale iv_size')
        self.iv_size = len(value)
        self._entry[INDICES["iv"]:INDICES["iv"] + self.iv_size] = value

    @property
    def main_block_num(self):
        return struct.unpack(
            ">I",
            self._entry[INDICES["main_block_num"]:INDICES["blank"]],
        )[0]

    @main_block_num.setter
    def main_block_num(self, value):
        self._entry[INDICES["main_block_num"]:INDICES["blank"]] = struct.pack(
            ">I",
            value,
        )

    @property
    def random(self):
        return str(self._entry[INDICES["random"]:INDICES["sha"]])

    @random.setter
    def random(self, value):
        self._entry[INDICES["random"]:INDICES["sha"]] = value

    @property
    def sha(self):
        return str(self._entry[INDICES["sha"]:INDICES["end"]])

    @sha.setter
    def sha(self, value):
        self._entry[INDICES["sha"]:INDICES["end"]] = value
