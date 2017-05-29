## @package client.services.bd_client_read
#
# Client service for requesting block read from block device server.
## @file bd_client_read.py Implementation of @ref client.services.bd_client_read
import base64
import logging

from common import constants
from common.services.service_base import ServiceBase

## Client read service class.
#
# requests block read from block device, then wakes up parent server.
#
class BDClientRead(ServiceBase):
    ## Class name.
    # @returns (str) name.
    @staticmethod
    def name():
        return constants.READ

    ## Constructor.
    # @param request_context (dict) request context.
    #
    # sets block read command with parameters provided from request context.
    # sets headers to match authorization with block device server.
    #
    def __init__(
        self,
        request_context,
    ):
        cmd = "GET /%s?block=%d %s\r\n" % (
            "read",
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

    ## Function called before receiveing HTTP response.
    # cleans up block reference for later read.
    def before_request_content(
        self,
        request_context,
    ):
        super(BDClientRead, self).before_request_content(request_context)
        request_context["block"] = ""

    ## Function called during receiving HTTP response.
    # adds read data to block until reaches block size.
    # @returns None if finished, (bool) True if there's more data in received buffer,
    # (bool) False if needs to receive more data in response.
    def handle_content(
        self,
        request_context,
    ):
        data = request_context["recv_buffer"][:request_context["content_length"]]
        request_context["recv_buffer"] = request_context["recv_buffer"][len(
            data):]
        request_context["block"] += data
        request_context["content_length"] -= len(data)
        if len(request_context["block"]) == constants.BLOCK_SIZE:
            return None
        else:
            return bool(request_context["recv_buffer"])

    ## Function called before sending HTTP headers.
    # overrides service base function to not send content length for nothing.
    def before_response_headers(
        self,
        request_context,
    ):
        return

    ## Function called before service termination
    # wakes up parent with fullly received block.
    def before_terminate(
        self,
        request_context,
    ):
        request_context["parent"].on_finish(block=request_context["block"])

    ## Get header dictionary.
    # @returns (dict) dictionary of wanted headers to parse.
    def get_header_dict(
        self,
    ):
        return {
            constants.CONTENT_LENGTH: 0
        }
