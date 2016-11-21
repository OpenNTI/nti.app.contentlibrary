#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Content-unit prefernce decorators.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from pyramid.interfaces import IRequest

from nti.app.contentlibrary.content_unit_preferences.prefs import prefs_present
from nti.app.contentlibrary.content_unit_preferences.prefs import find_prefs_for_content_and_user

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.interfaces import IContentUnitInfo

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

	def _predicate(self, context, result):
		return self._is_authenticated and context.contentUnit is not None

	def _do_decorate_external(self, context, result):
		prefs, provenance, contentUnit = \
					find_prefs_for_content_and_user(context.contentUnit, self.remoteUser)

		if prefs_present(prefs):
			ext_obj = {}
			ext_obj['State'] = 'set' if contentUnit is context.contentUnit else 'inherited'
			ext_obj['Provenance'] = provenance
			ext_obj['sharedWith'] = prefs.sharedWith
			ext_obj[CLASS] = 'SharingPagePreference'
			ext_obj[MIMETYPE] = 'application/vnd.nextthought.sharingpagepreference'
			result['sharingPreference'] = ext_obj

		if prefs:
			# We found one, but it specified no sharing settings.
			# we still want to copy its last modified
			if prefs.lastModified > context.lastModified:
				result[LAST_MODIFIED] = prefs.lastModified
				context.lastModified = prefs.lastModified
