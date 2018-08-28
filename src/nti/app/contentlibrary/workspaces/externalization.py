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

from nti.app.contentlibrary.workspaces.interfaces import ILibraryCollection

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import IExternalObject
from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

TOTAL = StandardExternalFields.TOTAL

logger = __import__('logging').getLogger(__name__)


@component.adapter(ILibraryCollection)
@interface.implementer(IExternalObject)
class LibraryCollectionDetailExternalizer(object):
    """
    Externalizes a Library wrapped as a collection.
    """

    # This doesn't do a good job of externalizing it,
    # though. We're skipping all the actual Collection parts

    def __init__(self, collection):
        self._collection = collection
    
    def toExternalObject(self, **kwargs):
        items = self._collection.library_items
        result = LocatedExternalDict(
            {
                'title': "Library",
                'titles': [
                    to_external_object(x, **kwargs) for x in items
                ]
            })
        result[TOTAL] = len(result['titles'])
        result.__name__ = self._collection.__name__
        result.__parent__ = self._collection.__parent__
        return result
