#!/usr/bin/python
import os

import constants
import util
from service_base import ServiceBase

class FileService(ServiceBase):
    @staticmethod
    def name():
        return "*"

    def __init__(
        self,
    ):
        super(FileService, self).__init__()

    def before_request_headers(
        self,
        request_context,
    ):
        try:
            file_name = os.path.normpath(
                '%s%s' % (
                    constants.BASE,
                    os.path.normpath(request_context["uri"]),
                )
            )
            fd = os.open(file_name, os.O_RDONLY)
            request_context["headers"][constants.CONTENT_LENGTH] = os.fstat(fd).st_size
            request_context["headers"][constants.CONTENT_TYPE] = constants.MIME_MAPPING.get(
                    os.path.splitext(
                        file_name
                    )[1].lstrip('.'),
                    'application/octet-stream',
                )
        except Exception as e:
            fd = None
            request_context["code"] = 500
            request_context["status"] = constants.INTERNAL_ERROR
            request_context["response"] = util.text_to_html(
                str(e)
            )
            request_context["headers"][constants.CONTENT_TYPE] = "text/html"
            request_context["headers"][constants.CONTENT_LENGTH] = len(request_context["response"])

        request_context["fd"] = fd

    def response(
        self,
        request_context,
    ):
        if not request_context["fd"]:
            return super(FileService, self).response(request_context)

        data = os.read(request_context["fd"], constants.BLOCK_SIZE - len(request_context["response"]))
        if not data:
            return None
        return data
