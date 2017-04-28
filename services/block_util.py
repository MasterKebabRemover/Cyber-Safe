import constants
import util
import integration_util
import logging

def bd_action(# should be called instead of read_block, write_block
    request_context,
    block_num,
    action,
    service_wake_up=None,
    block = None
):
    request_context["block_num"] = block_num
    if action == constants.READ:
        request_context["service_wake_up"] = service_wake_up
        request_context["read_block"] = None
        read_block(request_context)
    elif action == constants.WRITE:
        write_block(request_context, block)
    else:
        raise RuntimeError('Invalid action')

def read_block(
    request_context,
):
    if request_context.get("read_block") is None:
        # initialize
        request_context["read_block"] = bytearray(constants.BLOCK_SIZE)
        request_context["replies"] = 0
        request_context["wake_up_function"] = read_block
        request_context["state"] = constants.SLEEPING
        for d in request_context["app_context"]["devices"]:
            util.init_client(
                request_context,
                constants.READ,
                request_context["block_num"],
                block_device_num=d,
            )

    else:
        request_context["replies"] += 1
        request_context["read_block"] = integration_util.decrypt_data(
            request_context["read_block"],
            request_context["block"],
        )
        # if received all replies, wake up the service back
        if request_context.get("replies") == len(request_context["app_context"]["devices"]):
            request_context["block"] = request_context["read_block"]
            request_context["read_block"] = None
            request_context["service_wake_up"](request_context)
        else:
            request_context["state"] = constants.SLEEPING
            request_context["wake_up_function"] = read_block

def write_block(
    request_context,
    block,
):
    encrypted = integration_util.encrypt_data(block)
    for i in range(len(request_context["app_context"]["devices"])):
        util.init_client(
            request_context=request_context,
            client_action=constants.WRITE,
            client_block_num=request_context["block_num"],
            block=encrypted[i],
            block_device_num=request_context["app_context"]["devices"].keys()[i],
        )