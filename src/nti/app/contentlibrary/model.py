#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import time

from zope import interface
from zope import component

from nti.app.contentlibrary import BLOCKING_TIMEOUT
 
from nti.app.contentlibrary.interfaces import IContentUnitContents
from nti.app.contentlibrary.interfaces import IContentBundleCommunity
from nti.app.contentlibrary.interfaces import IContentTrackingRedisClient

from nti.dataserver.interfaces import IRedisClient

from nti.dataserver.users.communities import Community

from nti.property.property import alias

from nti.schema.fieldproperty import createDirectFieldProperties

from nti.schema.schema import SchemaConfigured


@interface.implementer(IContentUnitContents)
class ContentUnitContents(SchemaConfigured):
    createDirectFieldProperties(IContentUnitContents)

    mime_type = mimeType = 'application/vnd.nextthought.contentunit.contents'

    contents = alias('data')


@interface.implementer(IContentBundleCommunity)
class ContentBundleCommunity(Community):
    __external_can_create__ = False
    __external_class_name__ = 'Community'
    mime_type = mimeType = 'application/vnd.nextthought.contentbundlecommunity'


@interface.implementer(IContentTrackingRedisClient)
class ContentTrackingRedisClient(SchemaConfigured):
    createDirectFieldProperties(IContentTrackingRedisClient)

    def __init__(self, *args, **kwargs):
        SchemaConfigured.__init__(self, *args, **kwargs)

    def _mark_as_held(self, user):
        self.is_locked = True
        self.last_released = None
        self.last_locked = time.time()
        self.holding_user = user.username if user is not None else u''

    def _mark_as_released(self):
        self.holding_user = None
        self.is_locked = False
        self.last_locked = None
        self.last_released = time.time()

    def acquire_lock(self, user, lock_name, lock_timeout,
                     blocking_timeout=BLOCKING_TIMEOUT):
        redis = component.getUtility(IRedisClient)
        self.lock = redis.lock(lock_name,
                               lock_timeout,
                               blocking_timeout=blocking_timeout)
        acquired = self.lock.acquire(blocking=False)
        if acquired:
            self._mark_as_held(user)
        return acquired

    def release_lock(self, user):
        try:
            u_name = user.username if user is not None else u''
            if self.is_locked and u_name == self.holding_user:
                self.lock.release()
                self._mark_as_released()
        except Exception:
            pass

    def delete_lock(self, lock_name):
        redis = component.getUtility(IRedisClient)
        redis.delete(lock_name)
        self._mark_as_released()
