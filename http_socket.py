#!/usr/bin/python
import errno
import socket
import logging
import urlparse
import importlib

import constants
import util
from services import service_base
from pollable import Pollable
from collable import Collable

class HttpSocket(Pollable, Collable):
    request_context = {
        "code": 200,
        "status": "OK",
        "req_headers": {},
        "headers": {},
        "accounts": {},
        "content": "",
        "response": "",
        "recv_buffer": "",
        "send_buffer": "",
    }

    def __init__(
        self,
        socket,
        state,
        application_context,
        fd_dict,
        service_class=service_base.ServiceBase(),
    ):
        self._socket = socket
        self.state = state
        self._fd_dict = fd_dict
        self.request_context["application_context"] = application_context
        self._service_class = service_class
        for service in constants.MODULE_DICT[application_context["block_device"]]:
            importlib.import_module("services.%s" % service)

        self._state_machine = self._get_state_machine()
        self._current_state = constants.GET_FIRST_LINE

    def _get_state_machine(
        self,
    ):
        return {
            constants.GET_FIRST_LINE: {
                "func": self._get_first_line,
                "next": constants.GET_HEADERS,
            },
            constants.GET_HEADERS: {
                "func": self._get_headers,
                "next": constants.GET_CONTENT,
            },
            constants.GET_CONTENT: {
                "func": self._get_content,
                "next": constants.SEND_STATUS_LINE,
            },
            constants.SEND_STATUS_LINE: {
                "func": self._send_status_line,
                "next": constants.SEND_HEADERS,
            },
            constants.SEND_HEADERS: {
                "func": self._send_headers,
                "next": constants.SEND_RESPONSE,
            },
            constants.SEND_RESPONSE: {
                "func": self._send_response,
                "next": constants.GET_FIRST_LINE,
            },
        }

    def on_read(
        self,
    ):
        free_buffer_size = self.request_context[
            "application_context"
        ][
            "max_buffer_size"
        ] - len(
            self.request_context["recv_buffer"]
        )
        data = ""
        try:
            while len(data) < free_buffer_size:
                buffer = self._socket.recv(free_buffer_size - len(data))
                # logging.debug(buffer)
                if not buffer:
                    break
                data += buffer
        except socket.error as e:
            if e.errno != errno.EWOULDBLOCK:
                raise

        if not data:
            raise RuntimeError("Disconnect")
        self.request_context["recv_buffer"] += data
        self.on_receive()

    def on_receive(
        self,
    ):
        try:
            _call_me_again = None
            _call_me_again = call_me_again = self._state_machine[self._current_state]["func"]()
        except util.HTTPError as e:
            self.request_context["code"] = e.code
            self.request_context["status"] = e.status
            self.request_context["response"] = e.message
            self.request_context["headers"]["Content-Length"] = len(self.request_context["response"])
            self.request_context["headers"]["Content-Type"] = "text/plain"
            self._service_class = service_base.ServiceBase()
        if _call_me_again is None:
            _call_me_again = True
        return _call_me_again

    def on_write(
        self,
    ):
        try:
            while self.request_context["send_buffer"]:
                # logging.debug(self.request_context["send_buffer"])
                self.request_context["send_buffer"] = self.request_context["send_buffer"][
                    self._socket.send(self.request_context["send_buffer"]):
                ]
        except socket.error as e:
            if e.errno != errno.EWOULDBLOCK:
                raise

    def on_error(
        self,
    ):
        self.state = constants.CLOSING

    def on_close(
        self,
    ):
        self._socket.close()

    def on_finish(
        self,
    ):
        logging.debug("on finish was called")
        return

    def fileno(self):
        return self._socket.fileno()

    def _get_first_line(
        self,
    ):
        req, self.request_context["recv_buffer"] = util.recv_line(self.request_context["recv_buffer"])
        if not req:  # means that async server has yet to receive a full line
            return False
        req_comps = req.split(" ", 2)
        # logging.debug(req)
        # logging.debug(req_comps)
        if len(req_comps) != 3:
            raise RuntimeError("Incomplete HTTP protocol")
        if req_comps[2] != constants.HTTP_SIGNATURE:
            raise RuntimeError("Not HTTP protocol")

        method, uri, signature = req_comps
        if method not in constants.SUPPORTED_METHODS:
            raise RuntimeError(
                "HTTP unsupported method '%s'" % method,
            )
        if not uri or uri[0] != '/' or '\\' in uri:
            raise RuntimeError("Invalid URI")

        self.request_context["uri"] = uri
        self.request_context["parsed"] = urlparse.urlparse(uri)

        logging.debug(
            "fd %d called method %s" % (
                self.fileno(),
                self.request_context["parsed"].path
            )
        )

        REGISTRY = {
            service.name(): service for service in service_base.ServiceBase.__subclasses__()
        }
        if not REGISTRY.get("*"):
            REGISTRY["*"] = service_base.ServiceBase

        try:
            self._service_class = REGISTRY.get(
                self.request_context["parsed"].path,
                REGISTRY["*"],
            )()
        except KeyError:
            raise util.HTTPError(
                code=500,
                status="Internal Error",
                message="service not supported",
            )
        finally:
            self.request_context["req_headers"] = self._service_class.get_header_dict()
            self._current_state = self._state_machine[self._current_state]["next"]
            self._service_class.before_request_headers(self.request_context)

    def _get_headers(
        self,
    ):
        if util.get_headers(self.request_context):
            self._current_state = self._state_machine[self._current_state]["next"]
        self._service_class.before_request_content(self.request_context)

    def _get_content(
        self,
    ):
        util.get_content(self.request_context)
        while self._service_class.handle_content(self.request_context):
            pass
        if not self.request_context["content_length"]:
            self._service_class.before_response_status(self.request_context)
            self._current_state = self._state_machine[self._current_state]["next"]
        elif not self.request_context["recv_buffer"]:
            return False

    def _send_status_line(
        self,
    ):
        self.request_context["send_buffer"] += ((
                "%s %s %s\r\n"
            ) % (
                constants.HTTP_SIGNATURE,
                self.request_context["code"],
                self.request_context["status"],
            )
        ).encode("utf-8")
        self._service_class.before_response_headers(self.request_context)
        self._current_state = self._state_machine[self._current_state]["next"]

    def _send_headers(
        self,
    ):
        if util.send_headers(self.request_context):
            self._current_state = self._state_machine[self._current_state]["next"]
        self._service_class.before_response_content(self.request_context)

    def _send_response(
        self,
    ):
        data = None
        data = self._service_class.response(self.request_context)
        if data is None:
            self._service_class.before_terminate(self.request_context)
            self._resetrequest_context()
            self._current_state = self._state_machine[self._current_state]["next"]
        else:
            self.request_context["send_buffer"] += data
            return True
    
    def _resetrequest_context(
        self,
    ):
        self.request_context["code"] = 200
        self.request_context["status"] = "OK"
        self.request_context["req_headers"] = {}
        self.request_context["response"] = ""
        self.request_context["headers"] = {}
