#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: too many ancestors
# pylint: disable=I0011,R0901

from zope import interface

from zope.container.constraints import contains
from zope.container.constraints import containers

from zope.schema import Bytes as ValidBytes
from zope.schema import BytesLine as ValidBytesLine 

from zope.securitypolicy.interfaces import IRolePermissionManager

from nti.contentlibrary.interfaces import IContentUnit

from nti.coremetadata.interfaces import IRedisClient
# Content-specific boards and forums
# We define these as a distinct set of classes/interfaces/mimetypes/ntiids
# so that things like analytics and notable data can distinguish them.
# They are otherwise expected to be modeled exactly the same as community
# boards.

from nti.dataserver.contenttypes.forums.interfaces import IGeneralForum
from nti.dataserver.contenttypes.forums.interfaces import IUseOIDForNTIID
from nti.dataserver.contenttypes.forums.interfaces import IPublishableTopic
from nti.dataserver.contenttypes.forums.interfaces import IDefaultForumBoard
from nti.dataserver.contenttypes.forums.interfaces import IGeneralForumComment
from nti.dataserver.contenttypes.forums.interfaces import IGeneralHeadlinePost
from nti.dataserver.contenttypes.forums.interfaces import IGeneralHeadlineTopic

from nti.dataserver.interfaces import ICommunity
from nti.dataserver.interfaces import IShouldHaveTraversablePath

from nti.schema.field import List
from nti.schema.field import Float
from nti.schema.field import Bool
from nti.schema.field import Object
from nti.schema.field import TextLine as ValidTextLine


class IContentBundleCommunity(ICommunity):
    """
    A content bundle communiy
    """


class IContentBoard(IDefaultForumBoard,
                    IShouldHaveTraversablePath,
                    IUseOIDForNTIID):
    """
    A board belonging to a particular piece of content.
    """
    contains('.IContentForum')
    __setitem__.__doc__ = None


class IContentForum(IGeneralForum,
                    IShouldHaveTraversablePath):
    """
    A forum belonging to a particular piece of content.
    """
    containers(IContentBoard)
    contains('.IContentHeadlineTopic')
    __parent__.required = False


class IContentHeadlinePost(IGeneralHeadlinePost):
    """
    The headline of a content topic
    """
    containers('.IContentHeadlineTopic')
    __parent__.required = False


class IContentHeadlineTopic(IGeneralHeadlineTopic,
                            IPublishableTopic):
    containers(IContentForum)
    contains('.IContentCommentPost')
    __parent__.required = False
    headline = Object(IContentHeadlinePost,
                      title=u"The main, first post of this topic.")


class IContentCommentPost(IGeneralForumComment):
    containers(IContentHeadlineTopic)  # Adds __parent__ as required
    __parent__.required = False


# External client preferences

from zope.location.interfaces import ILocation

from nti.base.interfaces import ILastModified

from nti.contentfragments.interfaces import IUnicode


class IContentUnitPreferences(ILocation,
                              ILastModified):
    """
    Storage location for preferences related to a content unit.
    """
    # NOTE: This can actually be None in some cases, which makes it
    # impossible to validate this schema.
    sharedWith = List(value_type=Object(IUnicode),
                      title=u"List of usernames to share with")


class IContentPackageRolePermissionManager(IRolePermissionManager):
    """
    A role permission manager for ``IContentPackage``.
    """

    def initialize():
        """
        Initialize our role manager to default status.
        """

# App server

from nti.appserver.interfaces import INTIIDEntry


class IContentUnitInfo(INTIIDEntry):
    """
    Information about a particular bit of content and the links it contains.
    """

    contentUnit = Object(IContentUnit,
                         title=u"The IContentUnit this object provides info for, if there is one.",
                         description=u""" Typically this will only be provided for one-off requests.
                                    Bulk collections/requests will not have it.
                                    """)

# Mixins

class IContentUnitContents(interface.Interface):

    ntiid = ValidTextLine(title=u'Content unit NTIID')

    contentType = ValidBytesLine(
        title=u'Content Type',
        description=u'The content type identifies the type of data.',
        default=b'',
        required=False,
        missing_value=b''
    )

    data = ValidBytes(
        title=u'Data',
        description=u'The actual content of the object.',
        default=b'',
        missing_value=b'',
        required=False,
    )

class IContentTrackingRedisClient(interface.Interface):
    """
    Tracks the operations of an IRedisClient for metadata
    """
    redis = Object(IRedisClient,
                   title=u"Redis Client",
                   description=u"The Redis client")
    redis.setTaggedValue('_ext_excluded_out', True)
    
    last_released = Float(title=u"Last Released",
                         description=u"Timestamp of last Redis lock release",
                         default=None,
                         required=False)
    
    last_locked = Float(title=u"Last Locked",
                         description=u"Timestamp of last Redis lock",
                         default=None,
                         required=False)
    
    holding_user = ValidTextLine(title=u"Current User",
                            description=u"The current user holding the lock",
                            default=None,
                            required=False)
    
    is_locked = Bool(title=u"IsLocked",
                     description=u"If the Redis client is locked.",
                     default=False)
    
    def acquire_lock(self, lock_name, lock_timeout, blocking_timeout):
        """
        Attempt to acquire the Redis lock.
        """
    
    def release_lock(self):
        """
        Release Redis lock
        """
    
    def delete_lock(self):
        """
        Delete Redis lock
        """
