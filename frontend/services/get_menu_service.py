
## @package cyber-safe.frontend.services.get_menu_service
#
# a service for sending the HTML project GUI menu to browser.
#
import errno
import logging
import os

from common import constants
from common.services.service_base import ServiceBase

## Get menu service class.
class GetMenuService(ServiceBase):
    ## Class name function.
    # @returns (str) class name.
    # this class's name is "/" so it will be called when no arguments provided from browser.
    @staticmethod
    def name():
        return "/"

    ## Function called before sending HTTP status.
    # opens the html menu file and saves it's file descriptor for future use.
    def before_response_status(
        self,
        request_context,
    ):
        self._fd = os.open(
            request_context["app_context"]["base"] +
            "/html/menu.html",
            os.O_RDONLY,
            0o666)
        request_context["headers"][constants.CONTENT_LENGTH] = os.fstat(
            self._fd).st_size
        request_context["headers"][constants.CONTENT_TYPE] = "text/html"

        return True

    ## Function called during sending HTTP response content.
    # reads parts of html menu file and sends to browser.
    # finishes when read entire file.
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
            if e.errno not in (errno.EAGAIN, errno.EWOULDBLOCK):
                raise
