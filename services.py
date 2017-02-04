#!/usr/bin/python
import base64
import Cookie
import logging
import os
import tempfile
import time
import urlparse

import constants
import util

def get_registry():
    registry = {}
    for name, obj in globals().items():
        if hasattr(obj, "mro"):
            if ServiceBase in obj.mro():
                if obj.name():
                    registry[obj.name()] = obj
    return registry

class ServiceBase(object):
    def __init__(
        self,
    ):
        pass

    def before_first_line(
        self,
        request_context,
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
        request_context["content_length"] = int(
            request_context["req_headers"][constants.CONTENT_LENGTH]
        )

    def handle_content(
        self,
        request_context,
    ):
        return False

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
        result = request_context.get("response")
        if result is not None:
            del request_context["response"]
        return result

    def before_terminate(
        self,
        request_context,
    ):
        pass
    
    def get_header_dict(
        self,
    ):
        return {
            constants.CONTENT_LENGTH:0
        }

    @staticmethod
    def name():
        return None


class ClockService(ServiceBase):
    def __init__(
        self,
    ):
        super(ClockService, self).__init__()

    def before_response_headers(
        self,
        request_context,
    ):
        message = util.text_to_html(
            time.strftime("%H:%M:%S", time.localtime())
        )
        request_context["response"] = message
        request_context["headers"][constants.CONTENT_TYPE] = "text/html"
        super(ClockService, self).before_response_headers(request_context)

    @staticmethod
    def name():
        return "/clock"

class MultiplyService(ServiceBase):
    def __init__(
        self,
    ):
        super(MultiplyService, self).__init__()

    def before_response_headers(
        self,
        request_context,
    ):
        try:
            qs = urlparse.parse_qs(request_context["parsed"].query)
            result = int(qs['a'][0])*int(qs['b'][0])
            message = util.text_to_html(
                "The result is %s, my boy." % (result)
            )

        except Exception as e:
            request_context["code"] = 500
            request_context["status"] = constants.INTERNAL_ERROR
            message = util.text_to_html(
                str(e)
            )

        request_context["response"] = message
        request_context["headers"][constants.CONTENT_LENGTH] = len(message)
        request_context["headers"][constants.CONTENT_TYPE] = "text/html"

    @staticmethod
    def name():
        return "/mul"

class CounterService(ServiceBase):
    def __init__(
        self,
    ):
        super(CounterService, self).__init__()

    def before_request_content(
        self,
        request_context,
    ):
        c = Cookie.SimpleCookie()
        try:
            c.load(str(request_context["req_headers"].get(constants.Cookie)))
            if "counter" in c.keys():
                counter = c["counter"].value
            else:
                counter = 0
            c["counter"] = str(int(counter)+1)
            splitted = str(c["counter"]).split(":")
            request_context["counter"] = counter
            request_context["headers"][splitted[0]] = splitted[1]

        except Exception as e:
            request_context["code"] = 500
            request_context["status"] = constants.INTERNAL_ERROR
            request_context["counter"] = str(e)

    def before_response_headers(
        self,
        request_context,
    ):
        request_context["response"] = util.text_to_html(
            request_context["counter"]
        )
        request_context["headers"][constants.CONTENT_LENGTH] = len(request_context["response"])
        request_context["headers"][constants.CONTENT_TYPE] = "text/html"

    def get_header_dict(
        self,
    ):
        return {
            "Cookie":None
        }

    @staticmethod
    def name():
        return "/counter"

class SecretService1(ServiceBase):
    def __init__(
        self,
    ):
        super(SecretService1, self).__init__()

    def before_response_status(
        self,
        request_context,
    ):
        success = False
        authorization_header = request_context["req_headers"].get(constants.AUTHORIZATION)
        if authorization_header and authorization_header.split()[0] == "Basic":
            authorization = authorization_header.split("Basic ")[1]
            user, password = base64.b64decode(authorization).split(":", 1)
            if constants.USERS.get(user) == password:
                success = True
                request_context["user"] = user
        if success == False:
            request_context["code"] = 401
            request_context["status"] = "Unathorized"
            request_context["headers"] = {
                "WWW-Authenticate": "Basic",
            }

    def before_response_headers(
        self,
        request_context,
    ):
        if request_context.get("user"):
            request_context["response"] = util.text_to_html(
                "Welcome, %s!" % (request_context.get("user"))
            )
            request_context["headers"][constants.CONTENT_LENGTH] = len(request_context["response"])
            request_context["headers"][constants.CONTENT_TYPE] = "text/html"
        

    def get_header_dict(
        self,
    ):
        return {
            constants.AUTHORIZATION: None,
        }

    @staticmethod
    def name():
        return "/secret1"

class LoginService(ServiceBase):
    def __init__(
        self,
    ):
        super(LoginService, self).__init__()

    def before_response_headers(
        self,
        request_context,
    ):
        qs = urlparse.parse_qs(
            request_context["parsed"].query
        )
        user, password = qs["user"][0], qs["password"][0]
        cookies_to_set = {}
        code, status = 401, constants.UNATHORIZED
        message = "User and password incorrect"
        if constants.USERS.get(user) == password:
            cookie = util.random_cookie()

            for c, u in request_context["accounts"].copy().iteritems():
                if u == user:
                    del request_context["accounts"][c]

            request_context["accounts"][cookie] = user
            message = "Welcome, %s!" % (user)
            code, status = 200, "OK"
            cookies_to_set = "random=%s" % (cookie)
        request_context["code"] = code
        request_context["status"] = status
        request_context["headers"]["Set-Cookie"] = cookies_to_set
        request_context["response"] = util.text_to_html(message)
        request_context["headers"][constants.CONTENT_LENGTH] = len(
            request_context["response"],
        )
        request_context["headers"][constants.CONTENT_TYPE] = "text/html"
        

    def get_header_dict(
        self,
    ):
        return{}

    @staticmethod
    def name():
        return "/login"

class SecretService2(ServiceBase):
    def __init__(
        self,
    ):
        super(SecretService2, self).__init__()

    def get_header_dict(
        self,
    ):
        return{
            constants.Cookie: None,
        }

    def before_response_status(
        self,
        request_context,
    ):
        random = util.parse_cookies(request_context["req_headers"].get(constants.Cookie), "random")
        user = request_context["accounts"].get(random)
        if user:
            message = "Welcome, %s!" % (user)
            request_context["response"] = util.text_to_html(
                message,
            )
            request_context["headers"][constants.CONTENT_LENGTH] = len(
                request_context["response"]
            )
            request_context["headers"][constants.CONTENT_TYPE] = "text/html"
        else:
            request_context["code"] = 307
            request_context["status"] = "Temporary Redirect"
            request_context["headers"]["Location"] = "http://localhost:8888/loginform.html"

    @staticmethod
    def name():
        return "/secret2"

class FileUploadService(ServiceBase):
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

    @staticmethod
    def name():
        return "/fileupload"


class FileService(ServiceBase):
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

    @staticmethod
    def name():
        return "*"

class BlockDeviceRead(ServiceBase):
    def __init__(
        self,
    ):
        super(BlockDeviceRead, self).__init__()

    def before_response_status(
        self,
        request_context,
    ):

        sparse_size = os.stat(request_context["application_context"]["sparse"]).st_size
        qs = urlparse.parse_qs(request_context["parsed"].query)
        block = int(qs['block'][0])
        if (sparse_size / (1024*4)) - 1 < block:
            request_context["code"] = 500
            request_context["status"] = "Invalid block number"
        else:
            request_context["block"] = block

    def response(
        self,
        request_context,
    ):
        if request_context.get("block") is None:
            return
        sparse = os.open(request_context["application_context"]["sparse"], os.O_RDONLY)
        os.lseek(sparse, 1024*4*request_context["block"], os.SEEK_SET)
        data = os.read(sparse, 1024*4)
        os.close(sparse)
        request_context["block"] = None
        return data

    @staticmethod
    def name():
        return "/read"

class BlockDeviceWrite(ServiceBase):
    def __init__(
        self,
    ):
        super(BlockDeviceWrite, self).__init__()

    def before_response_status(
        self,
        request_context,
    ):

        sparse_size = os.stat(request_context["application_context"]["sparse"]).st_size
        qs = urlparse.parse_qs(request_context["parsed"].query)
        block = int(qs['block'][0])
        if (sparse_size / (1024*4)) - 1 < block:
            request_context["code"] = 500
            request_context["status"] = "Invalid block number"
        else:
            request_context["block"] = block

    def response(
        self,
        request_context,
    ):
        if request_context.get("block") is None:
            return
        sparse = os.open(request_context["application_context"]["sparse"], os.O_RDONLY)
        os.lseek(sparse, 1024*4*request_context["block"], os.SEEK_SET)
        data = os.read(sparse, 1024*4)
        os.close(sparse)
        request_context["block"] = None
        return data

    @staticmethod
    def name():
        return "/write"
