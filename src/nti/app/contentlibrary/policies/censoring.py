#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from nti.contentfragments import censor

from nti.contentfragments.interfaces import ICensoredContentPolicy

from nti.contentlibrary.interfaces import IDelimitedHierarchyContentUnit

from nti.dataserver.interfaces import IUser

logger = __import__('logging').getLogger(__name__)


@interface.implementer(ICensoredContentPolicy)
@component.adapter(IUser, IDelimitedHierarchyContentUnit)
def user_filesystem_censor_policy(unused_user, file_content_unit):
    """
    Profanity filtering may be turned off in specific content units
    by the use of a '.nti_disable_censoring' flag file.
    """
    # Maybe this could be handled with an ACL entry? The permission
    # to post uncensored things?
    if file_content_unit.does_sibling_entry_exist('.nti_disable_censoring'):
        return None
    return censor.DefaultCensoredContentPolicy()
