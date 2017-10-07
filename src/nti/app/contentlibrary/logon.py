#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component

from nti.app.contentlibrary.utils import update_users_content_roles

from nti.dataserver.users.interfaces import IOpenIDUserCreatedEvent

logger = __import__('logging').getLogger(__name__)


@component.adapter(IOpenIDUserCreatedEvent)
def _on_openid_user_created(event):
    idurl = event.idurl
    user = event.object
    content_roles = event.content_roles
    update_users_content_roles(user, idurl, content_roles)
