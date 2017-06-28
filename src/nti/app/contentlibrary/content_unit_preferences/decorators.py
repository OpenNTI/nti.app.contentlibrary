#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Content-unit prefernce decorators.

.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from pyramid.interfaces import IRequest

from nti.app.contentlibrary.content_unit_preferences.prefs import prefs_present
from nti.app.contentlibrary.content_unit_preferences.prefs import find_prefs_for_content_and_user

from nti.app.contentlibrary.interfaces import IContentUnitInfo

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalMappingDecorator

CLASS = StandardExternalFields.CLASS
MIMETYPE = StandardExternalFields.MIMETYPE
LAST_MODIFIED = StandardExternalFields.LAST_MODIFIED


@interface.implementer(IExternalMappingDecorator)
@component.adapter(IContentUnitInfo, IRequest)
class _ContentUnitPreferencesDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Decorates the mapping with the sharing preferences
    """

    CLASS = 'SharingPagePreference'
    MIME_TYPE = 'application/vnd.nextthought.sharingpagepreference'

    def _predicate(self, context, result):
        return self._is_authenticated and context.contentUnit is not None

    def find_prefs(self, contentUnit):
        return find_prefs_for_content_and_user(contentUnit, self.remoteUser)

    def _do_decorate_external(self, context, result):
        startUnit = context.contentUnit
        prefs, provenance, contentUnit = self.find_prefs(startUnit)

        if prefs_present(prefs):
            ext_obj = {}
            ext_obj[CLASS] = self.CLASS
            ext_obj[MIMETYPE] = self.MIME_TYPE
            ext_obj['State'] = 'set' if contentUnit is startUnit else 'inherited'
            ext_obj['Provenance'] = provenance
            ext_obj['sharedWith'] = prefs.sharedWith
            result['sharingPreference'] = ext_obj

        if prefs:
            # We found one, but it specified no sharing settings.
            # we still want to copy its last modified
            if prefs.lastModified > context.lastModified:
                result[LAST_MODIFIED] = prefs.lastModified
                context.lastModified = prefs.lastModified
