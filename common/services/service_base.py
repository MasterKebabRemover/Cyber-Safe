## @package cyber-safe.common.services.service_base
# Base class for all services.
import Cookie
import logging
import struct
import urlparse
import os

from common.utilities import block_util
from common import constants
from common.utilities import util

## Service Base class
# contains elementary functions for services to inherit and change.
# also conatains useful utilities.
class ServiceBase(object):
    ## Service name
    @staticmethod
    def name():
        return None

    ## Constructor.
    def __init__(
        self,
        request_context=None,
    ):
        pass

    ## Function called before receiving HTTP headers.
    def before_request_headers(
        self,
        request_context,
    ):
        pass

    ## Function called before receiving HTTP content.
    def before_request_content(
        self,
        request_context,
    ):
        pass

    ## Function called during receiving HTTP content.
    def handle_content(
        self,
        request_context,
    ):
        pass

    ## Function called before sending HTTP status.
    def before_response_status(
        self,
        request_context,
    ):
        pass

    ## Function called before sending HTTP headers.
    def before_response_headers(
        self,
        request_context,
    ):
        if constants.CONTENT_LENGTH not in request_context["headers"]:
            request_context["headers"][constants.CONTENT_LENGTH] = len(
                request_context["response"]
            )

    ## Function called before sending HTTP content.
    def before_response_content(
        self,
        request_context,
    ):
        pass

    ## Function called during sending HTTP content.
    def response(
        self,
        request_context,
    ):
        pass

    ## Function called before termination.
    def before_terminate(
        self,
        request_context,
    ):
        pass

    ## Get header dictionary.
    # @returns (dict) dictionary of wanted headers to parse.
    def get_header_dict(
        self,
    ):
        return {
            constants.CONTENT_LENGTH: 0,
            "Cookie": None,
        }

    ## Get user authorization
    # @returns (str) user authorization string.
    # checks query string and cookie headers for user authorization.
    # if found, return values. if not found, raise error.
    def get_authorization(
        self,
        request_context,
    ):
        authorization = None
        qs = urlparse.parse_qs(request_context["parsed"].query)
        authorization = qs.get('password', [None, None])[0]
        if authorization:
            c = Cookie.SimpleCookie()
            c["random"] = os.urandom(16)
            header = c.output().split(":")
            request_context["headers"][header[0]] = header[1]
            request_context["app_context"]["password_dict"][c["random"].value] = authorization
        else:
            random = util.parse_cookies(
                request_context["req_headers"].get("Cookie"), "random")
            authorization = request_context["app_context"]["password_dict"].get(
                random)

        if authorization:
            request_context["authorization"] = authorization
            return authorization
        else:
            request_context["headers"]["Location"] = "http://%s:%d/" % (
                request_context["app_context"]["bind_address"],
                request_context["app_context"]["bind_port"]
            )
            raise util.HTTPError(307, "Temporary Redirect")

    ## Parse core block.
    # @param request_context (dict) request context.
    # @param wake_up_function (function) function to call on finish.
    #
    # initializes client to read first, core block of block devices.
    # then wakes up next function to parse all bitmap and directory root blocks according to data found in core block.
    #
    def _parse_core(
        self,
        request_context,
        wake_up_function,
    ):
        self._wake_up_function = wake_up_function
        block_util.bd_action(
            request_context=request_context,
            block_num=0,
            action=constants.READ,
            service_wake_up=self._after_init,
        )

    ## After init block
    #
    # after receiving init, core block, starts reading all bitmaps into program.
    #
    def _after_init(
        self,
        request_context,
    ):
        init = bytearray(request_context["block"])
        if init[:len(constants.INIT_SIGNATURE)] != constants.INIT_SIGNATURE:
            raise util.HTTPError(500, "Internal Error", util.text_to_css("Disk not initialized", error=True))
        index = len(constants.INIT_SIGNATURE)
        self._bitmaps = struct.unpack(">B", init[index:index+1])[0]
        self._dir_roots = struct.unpack(">B", init[index+1:index+2])[0]
        self._current_bitmap = 1
        self._bitmap = bytearray(0)
        block_util.bd_action(
            request_context=request_context,
            block_num=self._current_bitmap,
            action=constants.READ,
            service_wake_up=self._construct_bitmap,
        )

    ## Construct bitmap.
    # this function wakes up after receiving bitmap, and if it's not the last then requests next bitmap part.
    # when entire bitmap construced, proceeds to wake up the directory root construction function.
    def _construct_bitmap(
        self,
        request_context,
    ):
        self._current_bitmap += 1
        self._bitmap += request_context["block"]
        if self._current_bitmap <= self._bitmaps:
            block_util.bd_action(
                request_context=request_context,
                block_num=self._current_bitmap,
                action=constants.READ,
                service_wake_up=self._construct_bitmap,
            )
        else:
            self._current_root = self._bitmaps + 1
            self._root = bytearray(0)
            block_util.bd_action(
                request_context=request_context,
                block_num=self._current_root,
                action=constants.READ,
                service_wake_up=self._construct_root,
            )

    ## Construct directory root
    # wakes up after receiving directory root part.
    # if not last part, requests next part and constructs entire directory root.
    def _construct_root(
        self,
        request_context,
    ):
        self._current_root += 1
        self._root += request_context["block"]
        if self._current_root <= self._dir_roots + self._bitmaps:
            block_util.bd_action(
                request_context=request_context,
                block_num=self._current_root,
                action=constants.READ,
                service_wake_up=self._construct_root,
            )
        else:
            self._wake_up_function(request_context)
