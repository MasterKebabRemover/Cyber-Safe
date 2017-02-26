#!/usr/bin/python
import socket

import constants
from pollable import Pollable

class TCPListener(Pollable):
    state = constants.LISTENER
    def __init__(
        self,
        bind_address,
        bind_port,
        initiate,
        application_context,
        fd_dict,
    ):
        self._initiate = initiate
        self._application_context = application_context
        self._fd_dict = fd_dict

        self.fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.fd.bind((bind_address, bind_port))
        self.fd.listen(10)
        self.fd.setblocking(False)

    def on_read(
        self,
    ):
        client, addr = self.fd.accept()
        self._fd_dict[client.fileno()] = self._initiate(
                socket=client,
                state=constants.ACTIVE,
                application_context=self._application_context,
                fd_dict=self._fd_dict
            )
    def on_write(self):
        pass

    def on_error(self):
        self.state = constants.CLOSING

    def on_close(self):
        self.fd.close()

    def fileno(self):
        return self.fd.fileno()
