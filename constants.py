#!/usr/bin/python
(
    SERVER,
    READING,
    WRITING,
    PROCESSING,
    CLOSING,
    LISTENER,
    ACTIVE,
) = range(7)

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
MODULE_DICT = {
    1: [
        "block_device_read_service",
        "block_device_write_service",
    ],
    0: [
        "clock_service",
        "counter_service",
        "file_service",
        "file_upload_service",
        "login_service",
        "multiply_service",
        "secret_service1",
        "secret_service2",
    ],
}

SUPPORTED_METHODS = ["GET", "POST"]
HTTP_SIGNATURE = "HTTP/1.1"
CRLF = "\r\n"
CRLF_BIN = CRLF.encode("utf-8")
MAX_NUMBER_OF_HEADERS = 100
Cookie = "Cookie"
BASE = "./files"
INTERNAL_ERROR = "Internal Error"
BLOCK_SIZE = 1024*4
CONTENT_TYPE = "Content-Type"
CONTENT_LENGTH = "Content-Length"
AUTHORIZATION = "Authorization"
UNATHORIZED = "Unathorized"
KB = 1024
MB = 1024*1024
