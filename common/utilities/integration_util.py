## @package cyber-safe.common.utilities.integration_util
#
# Various frontend-block_device integration related utilities.
#
import os
import logging

## Encrypt byte.
# @param byte (int) byte to split.
# @returns (tuple) two bytes that if xor'd together will give the initial encrypted byte.
#
# splits the bits of the byte into 2 bytes in random way, then xor's each with another random to increase security.
#
def encrypt_byte(byte):
    b1, b2 = 0, 0
    r = bytearray(os.urandom(1))[0]
    r2 = bytearray(os.urandom(1))[0]

    b1 = r & byte
    b2 = (~r) & byte

    return bytearray([r2 ^ b1]), bytearray([r2 ^ b2])

## Decrypt byte.
# @param b1 (int) first part.
# @param b2 (int) second part.
# @returns (bytearray) the xor result of the two byte parts.
def decrypt_byte(b1, b2):
    return bytearray([b1 ^ b2])

## Encrypt data.
# @param s (str) data to encrypt.
# @returns (list) data strings that if xor'd would give initial data.
#
# Uses byte Encrypt to split the data bits into different parts.
#
def encrypt_data(s):
    s1 = bytearray(0)
    s2 = bytearray(0)
    s = bytearray(s)
    for b in s:
        b1, b2 = encrypt_byte(b)
        s1 += b1
        s2 += b2
    return [s1, s2]

## Decrypt data.
# @param s1 (str) first part.
# @param s2 (str) second part.
# @returns (bytearray) the xor results of the 2 data parts' bytes.
def decrypt_data(s1, s2):
    s1, s2 = bytearray(s1), bytearray(s2)
    if len(s1) != len(s2):
        raise RuntimeError("string lengths do not match")
    s = bytearray(0)
    for i in range(len(s1)):
        s += decrypt_byte(s1[i], s2[i])
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
