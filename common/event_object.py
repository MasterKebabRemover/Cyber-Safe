#!/usr/bin/python
import select


class EventBase(object):
    def __init__(self):
        pass

    @staticmethod
    def name():
        return None

    def register(self, fd, mask):
        pass

    def unregister(self, fd):
        pass

    def poll(self, timeout):
        raise NotImplementedError()


class PollEvents(EventBase):
    def __init__(self):
        super(PollEvents, self).__init__()
        self._poll_object = select.poll()

    @staticmethod
    def name():
        return "poll"

    def register(self, fd, mask):
        self._poll_object.register(fd, mask)

    def unregister(self, fd):
        self._poll_object.unregister(fd)

    def poll(self, timeout):
        return self._poll_object.poll(timeout)


class SelectEvents(EventBase):
    def __init__(self):
        self._fd_dict = {}
        super(SelectEvents, self).__init__()

    @staticmethod
    def name():
        return "select"

    def register(self, fd, mask):
        self._fd_dict[fd] = mask

    def unregister(self, fd):
        del self._fd_dict[fd]

    def poll(self, timeout):
        events_dict = {}
        rlist, wlist, xlist = [], [], []
        mask_to_list = {
            select.POLLERR: xlist,
            select.POLLOUT: wlist,
            select.POLLIN: rlist,
        }

        for fd, mask in self._fd_dict.items():
            for select_mask in mask_to_list.keys():
                if fd not in mask_to_list[select_mask]:
                    if mask & select_mask:
                        mask_to_list[select_mask].append(fd)
                events_dict[fd] = 0

        r_ready, w_ready, x_ready = select.select(rlist, wlist, xlist, timeout)
        select_to_poll = {
            tuple(w_ready): select.POLLOUT,
            tuple(r_ready): select.POLLIN,
            tuple(x_ready): select.POLLERR,
        }
        for ready_list in select_to_poll.keys():
            for fd in ready_list:
                events_dict[fd] |= select_to_poll[ready_list]
        return events_dict.items()
