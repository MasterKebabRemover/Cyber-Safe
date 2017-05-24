
import logging
import os
import struct
import urlparse

from common.utilities import block_util
from common import constants
from common.utilities import util
from common.utilities import integration_util
from common.services.service_base import ServiceBase

class InitService(ServiceBase):
    @staticmethod
    def name():
        return "/init"

    def before_request_content(
        self,
        request_context,
    ):
        authorization = self.get_authorization(request_context)
        if authorization != request_context["app_context"]["admin"]:
            request_context["headers"][constants.CONTENT_TYPE] = "text/html"
            raise util.HTTPError(
                500,
                "Internal Error",
                util.text_to_css("Admin password required to init disk"),
            )

        # initialize disks
        qs = urlparse.parse_qs(request_context["parsed"].query)
        try:
            bitmaps, dir_roots = int(qs["bitmaps"][0]), int(qs["dir_roots"][0])
        except Exception:
            raise util.HTTPError(
                500,
                "Internal Error",
                util.text_to_css("Invalid parameters"),
            )
        if bitmaps > 255 or dir_roots > 255 or bitmaps < 1 or dir_roots < 1:
            raise util.HTTPError(
                500,
                "Internal Error",
                util.text_to_css("Parameters not in range [1, 255]"),
            )   
        init_block = bytearray(4096)
        init_block[0:len(constants.INIT_SIGNATURE)] = constants.INIT_SIGNATURE
        init_block[len(constants.INIT_SIGNATURE)] = struct.pack(">B", bitmaps)
        init_block[len(constants.INIT_SIGNATURE)+1] = struct.pack(">B", dir_roots)
        block_util.bd_action(
            request_context=request_context,
            block_num=0,
            action=constants.WRITE,
            block=init_block,
        )

        first_bitmap = bytearray(4096) # update first bitmap to include full blocks for bitmaps and roots
        index = 0
        blocks_to_fill = bitmaps + dir_roots + 1 # 1 is for init_block
        while blocks_to_fill:
            integration_util.bitmap_set_bit(first_bitmap, index,1)
            index += 1
            blocks_to_fill -= 1
        block_util.bd_action(
                request_context=request_context,
                block_num=1,
                action=constants.WRITE,
                block=first_bitmap,
            )
            
        for i in range(bitmaps - 1):
            block_util.bd_action(
                request_context=request_context,
                block_num=i+2,
                action=constants.WRITE,
                block=bytearray(4096),
            )
        for i in range(dir_roots):
            block_util.bd_action(
                request_context=request_context,
                block_num=bitmaps+i+1,
                action=constants.WRITE,
                block= bytearray(1) + os.urandom(
                    constants.BLOCK_SIZE - 1),
            )

    def before_response_headers(
        self,
        request_context,
    ):

        request_context["response"] = util.text_to_css(
            "disk initialized successfuly")
        request_context["response"] = util.text_to_html(
            request_context["response"])
        request_context["headers"][constants.CONTENT_TYPE] = "text/html"
        super(InitService, self).before_response_headers(request_context)
