## @package frontend.services.get_file_service
#
# a service for sending regular files to browser.
## @file get_file_service.py Implementation of @ref frontend.services.get_file_service
import errno
import logging
import os

from common import constants
from common.utilities import util
from common.services.service_base import ServiceBase

## Get file service class.
class GetFileService(ServiceBase):
    ## Class name function.
    # @returns (str) class name.
    @staticmethod
    def name():
        return "*"

    ## Function called before sending HTTP status.
    #
    # gets filename from query string, checks that this file is in base folder.
    # if it is, opens the file and saves the file descriptor for later use.
    #
    def before_response_status(
        self,
        request_context,
    ):
        filename = os.path.normpath(
            os.path.join(
                request_context["app_context"]["base"],
                request_context["parsed"].path[1:],
            )
        )
        base = request_context["app_context"]["base"]
        if filename[:-len(request_context["parsed"].path)
                    ] != os.path.normpath(base):
            raise RuntimeError("Malicious URI %s" %
                               request_context["parsed"].path)
        try:
            self._fd = os.open(filename, os.O_RDONLY, 0o666)
            request_context["headers"][constants.CONTENT_LENGTH] = os.fstat(
                self._fd).st_size
            request_context["headers"][constants.CONTENT_TYPE] = constants.MIME_MAPPING.get(
                os.path.splitext(filename)[1].lstrip('.'), constants.MIME_MAPPING["*"], )
        except OSError as e:
            if e.errno == errno.ENOENT:
                raise util.HTTPError(500, "Internal Error", util.text_to_css(
                    "File %s not found" % filename, error=True))
            if e.errno != errno.ENOENT:
                raise

        return True

    ## Function called during HTTP content sending.
    # uses previously saved file descriptor to read parts of the file and send them to client.
    # stops when entire file is sent.
    def response(
        self,
        request_context,
    ):

        buf = ""
        try:
            while len(request_context["response"]) < constants.BLOCK_SIZE:
                buf = os.read(self._fd, constants.BLOCK_SIZE)
                if not buf:
                    break
                request_context["response"] += buf

            if buf:
                return constants.RETURN_AND_WAIT
            os.close(self._fd)

        except Exception as e:
            logging.debug(e)
            if e.errno not in (errno.EAGAIN, errno.EWOULDBLOCK):
                raise
