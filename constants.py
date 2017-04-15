#!/usr/bin/python
(
    SERVER,
    READING,
    WRITING,
    PROCESSING,
    CLOSING,
    LISTENER,
    ACTIVE,
    SLEEPING,
    WAITING_FOR_DATA
) = range(9)

(
    GET_FIRST_LINE,
    GET_HEADERS,
    GET_CONTENT,
    SEND_STATUS_LINE,
    SEND_HEADERS,
    SEND_RESPONSE,
    TERMINATE,
) = range(7)

(
    CALL_SERVICE_AGAIN,
    RETURN_AND_WAIT,
    MOVE_TO_NEXT_STATE,
) = range(3)

MIME_MAPPING = {
    'html': 'text/html',
    'png': 'image/png',
    'txt': 'text/plain',
    'ico': 'image/x-icon',
    '*': 'text/plain',
}
USERS = {
    "ron": "spaghetti",
    "alon": "balon",
}
[READ, WRITE] = ["bd_client_read", "bd_client_write"]
MODULE_DICT = {
    1: [
        "block_device_read_service",
        "block_device_write_service",
    ],
    0: [
        "clock_service",
        "counter_service",
        "download_service",
        "file_upload_service",
        "login_service",
        "multiply_service",
        "secret_service1",
        "secret_service2",
        "list_files_service",
        "delete_service",
    ],
    "client": [
        "bd_client_read",
        "bd_client_write",
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
FILENAME_LENGTH = 60
ROOT_ENTRY_SIZE = 64
