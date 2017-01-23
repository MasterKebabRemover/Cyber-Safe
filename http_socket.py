#!/usr/bin/python
import logging
import urlparse

import constants
import services
import util

MAX_HEADER_LENGTH = 4096
MAX_HEADERS = 100
REGISTRY = services.get_registry()


class HttpSocket(object):
    current_state = constants.GET_FIRST_LINE
    _service_class = None
    _content = ""
    _request_context = {
        "code": 200,
        "status": "OK",
        "req_headers": {},
        "headers": {},
        "accounts": {},
        "content": "",
        "response": "",
    }
    send_buffer = ""
    recv_buffer = ""

    def __init__(
        self,
        socket,
        state,
        max_header_length=MAX_HEADER_LENGTH,
        max_headers=MAX_HEADERS,
    ):
        self.socket = socket
        self.state = state
        self._max_header_length = max_header_length
        self._max_headers = max_headers

        self._state_machine = self._get_state_machine()

    def _get_state_machine(
        self,
    ):
        return {
            constants.GET_FIRST_LINE: self._get_first_line,
            constants.GET_HEADERS: self._get_headers,
            constants.GET_CONTENT: self._get_content,
            constants.SEND_STATUS_LINE: self._send_status_line,
            constants.SEND_HEADERS: self._send_headers,
            constants.SEND_RESPONSE: self._send_response,
        }

    def on_receive(
        self,
    ):
        call_me_again = self._state_machine[self.current_state]()
        if call_me_again is None:
            call_me_again = True
        return call_me_again

    def _get_first_line(
        self,
    ):
        self._reset_request_context()
        req = self._recv_line()
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

        self._request_context["uri"] = uri
        self._request_context["parsed"] = urlparse.urlparse(uri)

        logging.debug(
            "fd %d called method %s" % (
                self.socket.fileno(),
                self._request_context["parsed"].path
            )
        )

        self._service_class = REGISTRY.get(
            self._request_context["parsed"].path,
            REGISTRY["*"],
        )()
        self._request_context["req_headers"] = self._service_class.get_header_dict()
        self._service_class.before_request_headers(self._request_context)

        self.current_state = constants.GET_HEADERS

    def _get_headers(
        self,
    ):
        for i in range(constants.MAX_NUMBER_OF_HEADERS):
            line = self._recv_line()
            if line is None: # means that async server has yet to receive all headers
                break

            if line == "": # this is the end of headers
                self._service_class.before_request_content(self._request_context)
                self.current_state = constants.GET_CONTENT
                break

            line = util.parse_header(line)
            if line[0] in self._request_context["req_headers"]:
                self._request_context["req_headers"][line[0]] = line[1]
        else:
            raise RuntimeError("Exceeded max number of headers")

    def _get_content(
        self,
    ):
        data = self.recv_buffer[:min(
            self._request_context["content_length"],
            constants.BLOCK_SIZE - len(self._request_context["content"]),
        )]
        self._request_context["content"] += data
        self._request_context["content_length"] -= len(data)
        if (
            not self._service_class.handle_content(self._request_context)
            and not self._request_context["content_length"]
            and not self._request_context["content"]
        ):
            self._service_class.before_response_status(self._request_context)
            self.current_state = constants.SEND_STATUS_LINE   

    def _send_status_line(
        self,
    ):
        self.send_buffer += ((
                "%s %s %s\r\n"
            ) % (
                constants.HTTP_SIGNATURE,
                self._request_context["code"],
                self._request_context["status"],
            )
        ).encode("utf-8")
        self._service_class.before_response_headers(self._request_context)
        self.current_state = constants.SEND_HEADERS

    def _send_headers(
        self,
    ):
        for key, value in self._request_context["headers"].iteritems():
            self.send_buffer += (
                "%s: %s\r\n" % (key, value)
            )
        self.send_buffer += ("\r\n")
        self._service_class.before_response_content(self._request_context)
        self.current_state = constants.SEND_RESPONSE
        

    def _send_response(
        self,
    ):
        data = self._service_class.response(self._request_context)
        if data is None:
            self.current_state = constants.GET_FIRST_LINE
        else:
            self.send_buffer += data

    def _recv_line(
        self,
    ):
        n = self.recv_buffer.find(constants.CRLF_BIN)
        if n == -1:
            return None

        result = self.recv_buffer[:n].decode("utf-8")
        self.recv_buffer = self.recv_buffer[n + len(constants.CRLF_BIN):]
        return result

    
    def _reset_request_context(
        self,
    ):
        self._request_context["code"] = 200
        self._request_context["status"] = "OK"
        self._request_context["req_headers"] = {}
        self._request_context["response"] = ""
        self._request_context["headers"] = {}

    def http_request(
        self,
        buffer,
    ):
        req, rest = self._recv_line(
            buffer,
            "",
        )
        req_comps = req.split(' ', 2)
        if req_comps[2] != constants.HTTP_SIGNATURE:
            raise RuntimeError('Not HTTP protocol')
        if len(req_comps) != 3:
            raise RuntimeError('Incomplete HTTP protocol')

    def http_response(
        self,
        code,
        status,
        message,
        headers={},
        length=0,
    ):
        buffer = ""

        if message and not length:
            length = len(message)

        buffer += (
            (
                "%s %s %s\r\n"
            ) % (
                constants.HTTP_SIGNATURE,
                code,
                status,
            )
        ).encode("utf-8")

        if not headers.get(constants.CONTENT_LENGTH):
            buffer += (
                (
                    "Content-Length: %s\r\n"
                ) % (
                    length,
                )
            ).encode("utf-8")

        for key, value in headers.iteritems():
            buffer += (
                "%s: %s\r\n" % (key, value)
            )
        buffer += ("\r\n")
        if message:
            buffer += (message)
        return buffer
