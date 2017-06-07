#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

from zope import component
from zope import interface

from zope.location.interfaces import LocationError

from zope.traversing.interfaces import ITraversable

from pyramid.interfaces import IRequest

from nti.contentlibrary.interfaces import IContentPackageLibrary


@interface.implementer(ITraversable)
@component.adapter(IContentPackageLibrary, IRequest)
class LibraryTraversable(object):

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def traverse(self, key, remaining_path):
        try:
            return self.context[key]
        except KeyError:
            raise LocationError(key)
