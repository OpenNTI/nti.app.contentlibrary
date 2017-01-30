#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from nti.contentfragments import censor

from nti.contentfragments.interfaces import ICensoredContentPolicy

from nti.contentlibrary.interfaces import IDelimitedHierarchyContentUnit

from nti.dataserver.interfaces import IUser


@interface.implementer(ICensoredContentPolicy)
@component.adapter(IUser, IDelimitedHierarchyContentUnit)
def user_filesystem_censor_policy(user, file_content_unit):
    """
    Profanity filtering may be turned off in specific content units
    by the use of a '.nti_disable_censoring' flag file.
    """
    # TODO: maybe this could be handled with an ACL entry? The permission
    # to post uncensored things?
    if file_content_unit.does_sibling_entry_exist('.nti_disable_censoring'):
        return None
    return censor.DefaultCensoredContentPolicy()
