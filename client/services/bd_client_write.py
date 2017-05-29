## @package client.services.bd_client_write
#
# Client service for requesting block write to block device server
## @file bd_client_write.py Implementation of @ref client.services.bd_client_write
import base64
import logging

from common import constants
from common.services.service_base import ServiceBase

## Client write service class.
#
# requests block write to block device.
#
class BDClientWrite(ServiceBase):
    ## Class name.
    # @returns (str) name.
    @staticmethod
    def name():
        return constants.WRITE

    ## Constructor.
    # @param request_context (dict) request context.
    #
    # sets block write command with parameters provided from request context.
    # sets headers to match authorization with block device server.
    #
    def __init__(
        self,
        request_context,
    ):
        cmd = "GET /%s?block=%d %s\r\n" % (
            "write",
            request_context["block_num"],
            constants.HTTP_SIGNATURE
        )
        request_context["send_buffer"] += cmd
        parent_context = request_context["parent"].request_context
        request_context["headers"]["Authorization"] = "Basic %s" % (
            base64.b64encode(
                "%s:%s" % (
                    parent_context["user_to_send"],
                    parent_context["password_to_send"],
                )
            )
        )

    ## Function called before sending HTTP headers.
    # sets proper content length header.
    def before_response_headers(
        self,
        request_context,
    ):
        request_context["headers"][constants.CONTENT_LENGTH] = constants.BLOCK_SIZE

    ## Function called during sending HTTP content.
    # sends to server the block provided by parent.
    def response(
        self,
        request_context,
    ):
        if request_context["block"]:
            data = request_context["block"]
            request_context["block"] = ""
            return data
        else:
            return None

    ## Function called before service termination
    # wakes up parent with fullly received block.
    def before_terminate(
        self,
        request_context,
    ):
        request_context["parent"].on_finish()

    ## Get header dictionary.
    # @returns (dict) dictionary of wanted headers to parse.
    def get_header_dict(
        self,
    ):
        return {
            constants.CONTENT_LENGTH: 0
        }
