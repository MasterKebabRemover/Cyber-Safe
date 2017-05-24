import base64
import hashlib
import hmac

def sha(data, *more_data):
    h = hmac.new(data, digestmod=hashlib.sha1)
    for i in more_data:
        h.update(i)
    return h.digest()

username = raw_input("Enter username: ")
password = raw_input("Enter password: ")
salt = raw_input("Enter salt: ")

print ("encrypted username: %s" % base64.b64encode(sha(username, salt)))
print ("encrypted password: %s" % base64.b64encode(sha(password, salt)))

while True:
    pass