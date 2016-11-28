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

# TODO: Fix this reference
from nti.appserver.workspaces.interfaces import ILibraryCollection

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import IExternalObject
from nti.externalization.interfaces import LocatedExternalDict

@component.adapter(ILibraryCollection)
@interface.implementer(IExternalObject)
class LibraryCollectionDetailExternalizer(object):
	"""
	Externalizes a Library wrapped as a collection.
	"""

	# TODO: This doesn't do a good job of externalizing it,
	# though. We're skipping all the actual Collection parts

	def __init__(self, collection):
		self._collection = collection

	def toExternalObject(self, **kwargs):
		library_items = self._collection.library_items
		result = LocatedExternalDict({
			'title': "Library",
			'titles' : [to_external_object(x, **kwargs) for x in library_items] })
		result.__name__ = self._collection.__name__
		result.__parent__ = self._collection.__parent__
		return result
