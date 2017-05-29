## @package common.constants
# Constants used within the program.
## @file constants.py Implementation of @ref common.constants

## Values to async server entry state.
# - CLOSING: Used when socket is about to be closed.
# - LISTENER: Used for listeners for accepting new connections.
# - ACTIVE: Used for all active sockets that are ready for read/write.
# - SLEEPING: Used for sleeping sockets who do not read/write.
#
(
    CLOSING,
    LISTENER,
    ACTIVE,
    SLEEPING,
) = range(4)

## HTTP state machine states.
# - GET_FIRST_LINE: State for receiving HTTP status line.
# - GET_HEADERS: State for receiving HTTP headers.
# - GET_CONTENT: State for receiving HTTP content.
# - SEND_STATUS_LINE: State for sending HTTP status line.
# - SEND_HEADERS: State for sending HTTP headers.
# - SEND_RESPONSE: State for sending HTTP content.
# - TERMINATE: State for service termination.
#
(
    GET_FIRST_LINE,
    GET_HEADERS,
    GET_CONTENT,
    SEND_STATUS_LINE,
    SEND_HEADERS,
    SEND_RESPONSE,
    TERMINATE,
) = range(7)

## Values to service return at HTTP state machine.
# - CALL_SERVICE_AGAIN: Command for calling the service function once more.
# - RETURN_AND_WAIT: Command for returning and waiting the next poll call.
# - MOVE_TO_NEXT_STATE: Command for switching state.
#
(
    CALL_SERVICE_AGAIN,
    RETURN_AND_WAIT,
    MOVE_TO_NEXT_STATE,
) = range(3)

## Supported Multipurpose Internet Mail Extensions.
MIME_MAPPING = {
    'html': 'text/html',
    'png': 'image/png',
    'txt': 'text/plain',
    'ico': 'image/x-icon',
    'css': 'text/css',
    '*': 'text/plain',
}

## Names of block device client services.
# - READ: Block read service.
# - WRITE: Block write service.
#
[READ, WRITE] = ["/bd_client_read", "/bd_client_write"]

## HTTP methods supported by server.
SUPPORTED_METHODS = ["GET", "POST"]
## HTTP signature
HTTP_SIGNATURE = "HTTP/1.1"
## Carriage return representation.
CRLF = "\r\n"
## Binary carriage return.
CRLF_BIN = CRLF.encode("utf-8")

## Maximum number of headers in HTTP request.
MAX_NUMBER_OF_HEADERS = 100
## Base location of files that client is allowed to request.
BASE = "./files/"

## Multipurpose block size for use at block device and frontend.
BLOCK_SIZE = 4096

CONTENT_TYPE = "Content-Type"
CONTENT_LENGTH = "Content-Length"
INTERNAL_ERROR = "Internal Error"
AUTHORIZATION = "Authorization"
UNATHORIZED = "Unathorized"

## Length of init vector for AES encryption.
IV_LENGTH = 16
## Size of root entry at file system.
ROOT_ENTRY_SIZE = 256
## Maximum allowed paralel readers from file system.
MAX_SEMAPHORE = 100
## Signature for indicating block device initialization.
INIT_SIGNATURE = "SIGNATURE"
## Length of randomly generated boundary at POST requests.
BOUNDARY_LENGTH = 10

## Dictionary containing all modules, divided to pollables using them.
# - 1: Modules used by block device.
# - 0: Modules used by frontend.
# - client: Modules used by client.
#
MODULE_DICT = {
    1: [
        "block_device.services.block_device_read_service",
        "block_device.services.block_device_write_service",
    ],
    0: [
        "frontend.services.get_menu_service",
        "frontend.services.get_file_service",
        "frontend.services.download_service",
        "frontend.services.file_upload_service",
        "frontend.services.list_files_service",
        "frontend.services.delete_service",
        "frontend.services.init_service",
        "frontend.services.admin_service",
    ],
    "client": [
        "client.services.bd_client_read",
        "client.services.bd_client_write",
    ],
}

## HTML text to add return to list button at user GUI
BACK_TO_LIST = """
    <br><form method="get" action="list">
    <input type="submit" value="Back to the file list">
    </form>
"""

## HTML text to add return to menu button at user GUI
BACK_TO_MENU = """
    <br><form method="get" action="html/menu.html">
    <input type="submit" value="Back to menu">
    </form>
"""

## HTML text to include css page design for response
RESPONSE_CSS = """
    <head>
    <link rel="stylesheet" href="css/status.css">
    </head>
"""
