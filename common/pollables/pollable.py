## @package common.pollables.pollable
# Base class of pollable objects with basic poll functions.
## @file pollable.py Implementation of @ref common.pollables.pollable
class Pollable(object):
    def on_read(self):
        return

    def on_write(self):
        return

    def on_error(self):
        return

    def on_close(self):
        return

    def fileno(self):
        return

    def on_idle(self):
        return

    def get_events(self):
        return
