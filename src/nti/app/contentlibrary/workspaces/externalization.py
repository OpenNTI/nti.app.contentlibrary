#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid.threadlocal import get_current_request

from requests.structures import CaseInsensitiveDict

from six.moves.urllib_parse import unquote

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

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

    @property
    def request(self):
        return get_current_request()

    @Lazy
    def params(self):
        params = self.request.params if self.request else {}
        return CaseInsensitiveDict(**params)

    @Lazy
    def searchTerm(self):
        # pylint: disable=no-member
        result = self.params.get('searchTerm') or self.params.get('filter')
        return unquote(result).lower() if result else None

    def search_prefix_match(self, compare, search_term):
        compare = compare.lower() if compare else ''
        for k in compare.split():
            if k.startswith(search_term):
                return True
        return compare.startswith(search_term)

    def search_include(self, bundle):
        result = True
        if self.searchTerm:
            op = self.search_prefix_match
            result = op(bundle.title, self.searchTerm)
        return result
    
    def toExternalObject(self, **kwargs):
        items = self._collection.library_items
        result = LocatedExternalDict(
            {
                'title': "Library",
                'titles': [
                    to_external_object(x, **kwargs) for x in items if self.search_include(x)
                ]
            })
        result[TOTAL] = len(result['titles'])
        result.__name__ = self._collection.__name__
        result.__parent__ = self._collection.__parent__
        return result
