#!/usr/bin/python
## @package common.utilities.integration_util
#
# Various frontend-block_device integration related utilities.
## @file integration_util.py Implementation of @ref common.utilities.integration_util
import os
import logging
import struct

## Encrypt byte.
# @param byte (str) byte to split.
# @param copies (int) number of copies to create.
# @returns (list) bytes that if xor'd together will give the initial encrypted byte.
#
# splits the bits of the byte into a list of bytes of length copies in random way, then xor's each with another random to increase security.
#
def encrypt_byte(byte, copies):
    result = []
    for i in range(copies):
        result.append(0)

    r = ord(os.urandom(1))

    for i in range(8):
        bit = get_bit(i, byte)
        r2 = ord(os.urandom(1)) % len(result)
        result[r2] = set_bit(i, bit, result[r2])

    for i in range(copies):
        result[i] ^=  r

    if copies % 2 == 1:
        result[-1] ^= r

    return result

## Decrypt byte.
# @param byte_list (list) list of bytes.
# @returns (bytearray) the xor result of the bytes in byte list.
def decrypt_byte(byte_list):
    result = 0
    for i in byte_list:
        result ^= i
    return result

## Encrypt data.
# @param data (bytearray) data to encrypt.
# @param copies (int) copies to create
# @returns (list) data strings that if xor'd would give initial data.
#
# Uses byte Encrypt to split the data bits into different parts.
#
def encrypt_data(data, copies):
    result = []
    for i in range(copies):
        result.append(bytearray(0))
    for byte in data:
        bytes_to_add = encrypt_byte(byte, copies)
        for i in range(copies):
            result[i] += chr(bytes_to_add[i])
    return result

## Decrypt data.
# @param data_list (list) list of data parts.
# @returns (bytearray) the xor results of the data parts' bytes.
def decrypt_data(data_list):
    for i in data_list:
        i = bytearray(i)
    s = bytearray(0)
    for i in range(len(data_list[0])):
        byte_list = []
        for d in data_list:
            byte_list.append(ord(d[i:i+1]))
        s += chr(decrypt_byte(byte_list))
    return s

## Get bit of byte.
# @param bit (int) bit index in byte.
# @param byte (str) byte.
# @returns (int) target bit value in target byte.
def get_bit(bit, byte):
    if bit > 7:
        raise RuntimeError('bit must be between 0 and 7')
    if byte ^ (byte & 2**bit) == byte:
        return 0
    return 1

## Set bit of byte.
# @param bit (int) bit index in byte.
# @param (value) value of bit to set.
# @param (byte) byte.
# @returns (int) byte after setting target value of target bit.
def set_bit(bit, value, byte):
    if value not in (0, 1):
        raise RuntimeError('value must bee 0 or 1')
    if bit > 7:
        raise RuntimeError('bit must be between 0 and 7')
    if value == 1:
        return byte | (2**bit)
    else:
        return byte - (2**bit) * get_bit(bit, byte)

## Get bit from bitmap
# @param bitmap (bytearray) bitmap.
# @param bit (int) bit index in bitmap.
# @returns (int) value of target bit from bitmap.
def bitmap_get_bit(bitmap, bit):  # gets bit from bitmap
    return get_bit(bit % 8, bitmap[bit / 8])

## Set bit in bitmap.
# @param bitmap (bytearray) bitmap.
# @param bit (int) bit index in bitmap.
# @param value (int) bit value to set.
# @returns (bytearray) bitmap after setting value of target bit.
def bitmap_set_bit(bitmap, bit, value):  # sets bit of bitmap to value
    bitmap[bit / 8] = set_bit(
        bit % 8,
        value,
        bitmap[bit / 8]
    )
    return bitmap