#!/usr/bin/python
## @package common.utilities.userpass_encryption_tool
#
# A simple tool, independent of program main.
# Used by input of username, password and salt.
# returns value of hashed username and password to set in block device config files.
## @file userpass_encryption_tool.py Implementation of @ref block_device.userpass_encryption_tool
import argparse
import base64
import hashlib
import hmac

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "username",
        help="username to hash",
    )
    parser.add_argument(
        "password",
        help="password to hash",
    )
    parser.add_argument(
        "salt",
        help="salt for hash",
    )

    args = parser.parse_args()
    return args

def sha(data, *more_data):
    h = hmac.new(data, digestmod=hashlib.sha1)
    for i in more_data:
        h.update(i)
    return h.digest()

args = parse_args()

print ("encrypted username: %s" % base64.b64encode(sha(args.username, args.salt)))
print ("encrypted password: %s" % base64.b64encode(sha(args.password, args.salt)))
print ("base64 salt: %s" % base64.b64encode(args.salt))