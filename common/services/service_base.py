
import Cookie
import logging
import struct
import urlparse
import os

from common.utilities import block_util
from common import constants
from common.utilities import util


class ServiceBase(object):
    @staticmethod
    def name():
        return None

    def __init__(
        self,
        request_context=None,
    ):
        pass

    def before_request_headers(
        self,
        request_context,
    ):
        pass

    def before_request_content(
        self,
        request_context,
    ):
        pass

    def handle_content(
        self,
        request_context,
    ):
        pass

    def before_response_status(
        self,
        request_context,
    ):
        pass

    def before_response_headers(
        self,
        request_context,
    ):
        if constants.CONTENT_LENGTH not in request_context["headers"]:
            request_context["headers"][constants.CONTENT_LENGTH] = len(
                request_context["response"]
            )

    def before_response_content(
        self,
        request_context,
    ):
        pass

    def response(
        self,
        request_context,
    ):
        pass

    def before_terminate(
        self,
        request_context,
    ):
        pass

    def get_header_dict(
        self,
    ):
        return {
            constants.CONTENT_LENGTH: 0,
            "Cookie": None,
        }

    def get_authorization(
        self,
        request_context,
    ):
        # check query and cookie headers. if neither exist, raise error. if any
        # exists, put it in request_context and return it.
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

    def bd_authorization( # checks whether request authorization matches data in config
        self,
        request_context,
    ):
        config = request_context["app_context"]["config"]
        password_hash = config.get('blockdevice', 'password_hash')
        salt = config.get('blockdevice', 'salt')

    def _parse_core( # used to parse init block and get core parts: bitmap and directory root
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
