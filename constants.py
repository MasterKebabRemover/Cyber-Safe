#!/usr/bin/python
(
    SERVER,
    READING,
    WRITING,
    PROCESSING,
    CLOSING,
) = range(5)

(
    GET_FIRST_LINE,
    GET_HEADERS,
    GET_CONTENT,
    SEND_STATUS_LINE,
    SEND_HEADERS,
    SEND_RESPONSE,
) = range(6)

MIME_MAPPING = {
    'html': 'text/html',
    'png': 'image/png',
    'txt': 'text/plain',
    'ico': 'image/x-icon',
}
USERS = {
    "ron": "spaghetti",
    "alon": "balon",
}
SUPPORTED_METHODS = ["GET", "POST"]
HTTP_SIGNATURE = "HTTP/1.1"
CRLF = "\r\n"
CRLF_BIN = CRLF.encode("utf-8")
MAX_NUMBER_OF_HEADERS = 100
Cookie = "Cookie"
BASE = "./files"
INTERNAL_ERROR = "Internal Error"
BLOCK_SIZE = 1024
CONTENT_TYPE = "Content-Type"
CONTENT_LENGTH = "Content-Length"
AUTHORIZATION = "Authorization"
UNATHORIZED = "Unathorized"
