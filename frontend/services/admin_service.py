## @package frontend.services.admin_service
#
# simple service for verifying admin authentication. 
## @file admin_service.py Implementation of @ref frontend.services.admin_service
import logging

from common import constants
from common.utilities import util
from common.services.service_base import ServiceBase

## Admin service class.
class AdminService(ServiceBase):
    ## Class name function.
    # @returns (str) class name.
    @staticmethod
    def name():
        return "/admin"

    ## Function called before receiving HTTP content.
    #
    # checks query authorization and compares it to admin data from app_context.
    # if no match, redirects to error page. if match, redirects to admin control page.
    #
    def before_request_content(
        self,
        request_context,
    ):
        if self.get_authorization(
                request_context) != request_context["app_context"]["admin"]:
            request_context["headers"][constants.CONTENT_TYPE] = "text/html"
            raise util.HTTPError(500, "Internal Error", util.text_to_css(
                "Admin password required", error=True))
        request_context["code"] = 307
        request_context["status"] = "Temporary Redirect"
        request_context["headers"]["Location"] = "html/admin.html"
