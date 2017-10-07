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

from zope.location.interfaces import LocationError

from zope.traversing.interfaces import ITraversable

from pyramid.interfaces import IRequest

from nti.contentlibrary.interfaces import IContentPackageLibrary

logger = __import__('logging').getLogger(__name__)


@interface.implementer(ITraversable)
@component.adapter(IContentPackageLibrary, IRequest)
class LibraryTraversable(object):

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def traverse(self, key, unused_remaining_path):
        try:
            return self.context[key]
        except KeyError:
            raise LocationError(key)
