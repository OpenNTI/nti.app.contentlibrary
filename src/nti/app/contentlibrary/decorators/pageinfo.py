#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from pyramid.interfaces import IRequest

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.app.contentlibrary.interfaces import IContentUnitInfo

from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IContentUnitHrefMapper

from nti.externalization.interfaces import IExternalMappingDecorator

from nti.traversal.traversal import find_interface


@component.adapter(IContentUnitInfo, IRequest)
@interface.implementer(IExternalMappingDecorator)
class _ContentUnitInfoDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _predicate(self, context, unused_result):
        return self._is_authenticated and context.contentUnit is not None

    def _do_content_package(self, context, result):
        try:
            unit = context.contentUnit
            package = find_interface(unit, IContentPackage, strict=False)
            if package is not None:
                result['ContentPackageNTIID'] = package.ntiid
        except AttributeError:
            pass

    def _do_content_root(self, context, result):
        unit = context.contentUnit
        package = find_interface(unit, IContentPackage, strict=False)
        if package is not None:
            try:
                mapper = IContentUnitHrefMapper(package.key.bucket, None)
                if mapper is not None:
                    result['RootURL'] = mapper.href
            except AttributeError:
                pass

    def _do_content_title(self, context, result):
        try:
            title = context.contentUnit.title
            result['Title'] = title
        except AttributeError:
            pass

    def _do_decorate_external(self, context, result):
        self._do_content_root(context, result)
        self._do_content_title(context, result)
        self._do_content_package(context, result)
