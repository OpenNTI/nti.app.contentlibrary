#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views for exposing the content library to clients.

In addition to providing access to the content, this

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import time

from zope import component
from zope import interface

from zope.annotation.factory import factory as an_factory

from persistent import Persistent

from nti.app.contentlibrary.content_unit_preferences.interfaces import IContentUnitPreferences

from nti.containers.containers import LastModifiedBTreeContainer

from nti.contentlibrary.interfaces import IDelimitedHierarchyContentUnit

# We look for content container preferences. For actual containers, we
# store the prefs as an annotation on the container.
# NOTE: This requires that the user must have created at least one object
# on the page before they can store preferences.

@interface.implementer(IContentUnitPreferences)
@component.adapter(LastModifiedBTreeContainer)  # see also the field namespace registration
class _ContentUnitPreferences(Persistent):

	__parent__ = None
	__name__ = None
	sharedWith = None

	def __init__(self, createdTime=None, lastModified=None, sharedWith=None):
		self.createdTime = createdTime if createdTime is not None else time.time()
		self.lastModified = lastModified if lastModified is not None else self.createdTime
		if sharedWith is not None:
			self.sharedWith = sharedWith

# For BWC, use the old data.
ANNOTATION_KEY = u'nti.appserver.contentlibrary.library_views._ContentUnitPreferences'
_ContainerContentUnitPreferencesFactory = an_factory(_ContentUnitPreferences,
													 key=ANNOTATION_KEY)

# We can also look for preferences on the actual content unit
# itself. We provide an adapter for IDelimitedHierarchyContentUnit, because
# we know that :mod:`nti.contentlibrary.eclipse` may set up sharedWith
# values for us.

@interface.implementer(IContentUnitPreferences)
@component.adapter(IDelimitedHierarchyContentUnit)
def _DelimitedHierarchyContentUnitPreferencesFactory(content_unit):
	sharedWith = getattr(content_unit, 'sharedWith', None)
	if sharedWith is None:
		return None

	prefs = _ContentUnitPreferences(createdTime=time.mktime(content_unit.created.timetuple()),
									lastModified=time.mktime(content_unit.modified.timetuple()),
									sharedWith=content_unit.sharedWith)
	prefs.__parent__ = content_unit
	return prefs
