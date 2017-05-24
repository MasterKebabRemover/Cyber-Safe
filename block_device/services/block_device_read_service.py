
import os
import urlparse

from common import constants
from common.utilities import util
from common.services.service_base import ServiceBase
from common.utilities import encryption_util


class BlockDeviceRead(ServiceBase):
    @staticmethod
    def name():
        return "/read"

    def before_response_status(
        self,
        request_context,
    ):
        if not encryption_util.check_login(request_context):
            raise util.HTTPError(401, "Unathorized", "Bad block device authentication")
        sparse_size = os.stat(request_context["app_context"]["sparse"]).st_size
        qs = urlparse.parse_qs(request_context["parsed"].query)
        block = int(qs['block'][0])
        if block >= sparse_size / constants.BLOCK_SIZE:
            raise util.HTTPError(500, "Invalid block number")
        else:
            request_context["block"] = block

    def before_response_headers(
        self,
        request_context,
    ):
        request_context["headers"][constants.CONTENT_LENGTH] = constants.BLOCK_SIZE

    def response(
        self,
        request_context,
    ):
        if request_context["block"] is not None:
            data = bytearray(0)
            with util.FDOpen(
                request_context["app_context"]["sparse"],
                os.O_RDONLY,
            ) as fd:
                os.lseek(
                    fd,
                    constants.BLOCK_SIZE * request_context["block"],
                    os.SEEK_SET,
                )
                while len(data) < constants.BLOCK_SIZE:
                    read_buffer = os.read(fd, constants.BLOCK_SIZE - len(data))
                    if not read_buffer:
                        break
                    data += read_buffer
            # now decrypt data by block device keys
            aes = encryption_util.get_aes(
                key=request_context["app_context"]["config"].get(
                    'blockdevice', 'key'),
                ivkey=request_context["app_context"]["config"].get(
                    'blockdevice', 'ivkey'),
                block_num=request_context["block"],
            )
            data = encryption_util.decrypt_block_aes(aes, data)

            request_context["block"] = None
            request_context["response"] = data

    def get_header_dict(
        self,
    ):
        return {
            constants.AUTHORIZATION: None,
        }
