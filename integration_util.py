import random
import struct

def xor_bytes(b1, b2):
    return ''.join(chr(ord(a) ^ ord(b)) for a,b in zip(b1, b2))

def encrypt_byte(b):
    r1 = chr(random.randint(0, 255))
    r2 = chr(random.randint(0, 255))
    return xor_bytes(b, r1), r1

def decrypt_byte(b1, b2):
    return xor_bytes(b1, b2)

def encrypt_data(s):
    s1 = ""
    s2 = ""
    for b in bytes(s):
        b1, b2 = encrypt_byte(b)
        s1 += b1
        s2 += b2
    return s1, s2

def decrypt_data(s1, s2):
    if len(s1) != len(s2):
        raise RuntimeError("string lengths do not match")

    s = ""
    for i in range(len(s1)):
        s += decrypt_byte(s1[i], s2[i])
    return s

s1, s2 = encrypt_data('nice meme')
print (s1, s2)
print decrypt_data(s1, s2)
    
    