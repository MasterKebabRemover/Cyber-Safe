#!/usr/bin/python
import os

def encrypt_byte(byte): # return 2 random bytes that if xor'd would give the initial byte
    b1, b2 = 0, 0
    r = bytearray(os.urandom(1))[0]
    r2 = bytearray(os.urandom(1))[0]

    b1 = r & byte
    b2 = (~r) & byte

    return bytearray([r2^b1]), bytearray([r2^b2])

def decrypt_byte(b1, b2): # xor's the 2 bytes but returns string instead of int
    return bytearray([b1^b2])

def encrypt_data(s): # returns 2 random  byte arrays that if xor'd would give the initial byte array
    s1 = bytearray(0)
    s2 = bytearray(0)
    for b in s:
        b1, b2 = encrypt_byte(b)
        s1 += b1
        s2 += b2
    return s1, s2

def decrypt_data(s1, s2): # xor's the 2 byte arrays and returns the original byte array
    if len(s1) != len(s2):
        raise RuntimeError("string lengths do not match")
    s = bytearray(0)
    for i in range(len(s1)):
        s += decrypt_byte(s1[i], s2[i])
    return s

def xor_bytes(b1, b2): #xor's 2 bytes, receives and returns strings
    return bytearray([bytearray(b1)[0] ^ bytearray(b2)[0]])

def get_bit(bit, byte): # get bit from byte
    if bit > 7:
        raise RuntimeError('bit must be between 0 and 7')
    if byte ^ (byte & 2**bit) == byte:
        return 0
    return 1

def set_bit(bit, value, byte): # set bit of byte to value
    if value not in (0, 1):
        raise RuntimeError('value must bee 0 or 1')
    if bit > 7:
        raise RuntimeError('bit must be between 0 and 7')
    if value == 1:
        return byte | (2**bit)
    else:
        return byte - (2**bit)*get_bit(bit, byte)

def bitmap_get_bit(bitmap, bit): # gets bit from bitmap
    return get_bit(bit % 8, bitmap[bit/8])

def bitmap_set_bit(bitmap, bit, value): # sets bit of bitmap to value
    bitmap[bit/8] = set_bit(
        bit % 8,
        value,
        bitmap[bit/8]
    )
    return bitmap


# s = bytearray("this is working")
# s1, s2 = encrypt_data(s)
# print decrypt_data(s1, s2)