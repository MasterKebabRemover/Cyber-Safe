#!/usr/bin/python
import os
import tempfile

import constants
import util
from service_base import ServiceBase

class FileUploadService(ServiceBase):
    @staticmethod
    def name():
        return "/fileupload"

    def __init__(
        self,
    ):
        super(FileUploadService, self).__init__()
        self._current_func = self._recv_headers

    def before_request_content(
        self,
        request_context,
    ):
        super(FileUploadService, self).before_request_content(request_context)
        request_context["boundary"] = "--"
        request_context["boundary"] += bytearray(
            request_context["req_headers"][constants.CONTENT_TYPE].split(
                "boundary="
            )[1].encode("utf-8")
        )
        request_context["final_boundary"] = request_context["boundary"] + "--"
        request_context["boundary"] += "\r\n"
        request_context["final_boundary"] += "\r\n"

        request_context["req_headers"]["Content-Disposition"] = None
        request_context["req_headers"]["Content-Type"] = None

        request_context["response"] = "The files:\r\n"  # prepare reply in case of success

    def _recv_headers(
        self,
        request_context,
    ):
        line, request_context["content"] = util.recv_line(request_context["content"])
        while line is not None:
            if line == "":
                self._init_file(request_context)
                self._current_func = self._recv_content
                break
            else:
                line = util.parse_header(line)
                if line[0] in request_context["req_headers"]:
                    request_context["req_headers"][line[0]] = line[1]
                line, request_context["content"] = util.recv_line(request_context["content"])
        if len(request_context["content"]) > constants.BLOCK_SIZE:
            raise RuntimeError("Maximum header size reached")

    def _init_file(
        self,
        request_context,
    ):
        cd = request_context["req_headers"]["Content-Disposition"].split("; ")
        request_context["filename"] = None
        request_context["fd"] = None
        for field in cd:
            if len(field.split("filename=")) == 2:
                request_context["filename"] = field.split("filename=")[1].strip("\"")
        if not request_context["filename"]:
            request_context["code"] = 400
            request_context["status"] = "Bad Request"
        else:
            request_context["fd"], request_context["filepath"] = tempfile.mkstemp(
                dir="./downloads"
            )

    def _recv_content(
        self,
        request_context,
    ):
        while request_context["content"][:-len(request_context["boundary"])]:
            index = request_context["content"].find(request_context["boundary"])
            if index == 0:
                break
            request_context["content"] = request_context["content"][
                os.write(
                    request_context["fd"],
                    request_context["content"][:index],
                ):
            ]
        
    def handle_content(
        self,
        request_context,
    ):
        request_context["content"] = request_context["content"].replace(
            request_context["final_boundary"],
            request_context["boundary"],
        )
        index = request_context["content"].find(request_context["boundary"])
        if index == -1:
            self._current_func(
                request_context,
            )
        else:
            while request_context["content"].find(request_context["boundary"]) != 0:
                self._current_func(
                    request_context,
                )
            request_context["content"] = request_context["content"][len(
                request_context["boundary"]
            ):]
            if self._current_func == self._recv_content:
                self._current_func = self._recv_headers
                os.rename(
                    request_context["filepath"], "%s/%s" % (
                        os.path.dirname(request_context["filepath"]),
                        request_context["filename"]
                    )
                )
                os.close(request_context["fd"])
                request_context["response"] += "%s\r\n" % (request_context["filename"])
        if request_context["content"][:-len(request_context["boundary"])]:
            return True
        return False

    def before_response_headers(
        self,
        request_context,
    ):
        if request_context["code"] == 200:
            request_context["response"] += "Were uploaded successfully"
        request_context["response"] = util.text_to_html(request_context["response"])
        request_context["headers"][constants.CONTENT_TYPE] = "text/html"
        super(FileUploadService, self).before_response_headers(request_context)

    def get_header_dict(
        self,
    ):
        return (
            {
                constants.CONTENT_LENGTH:0,
                constants.CONTENT_TYPE:None,
            }
        )
