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

import sys
import time

from zope import component

from pyramid import httpexceptions as hexc

from pyramid.view import view_config

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentlibrary.content_unit_preferences.interfaces import IContentUnitPreferences

from nti.app.contentlibrary.views.library_views import _LibraryTOCRedirectView
from nti.app.contentlibrary.views.library_views import _RootLibraryTOCRedirectView

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.dataserver import authorization as nauth

from nti.ntiids import ntiids

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 context=IContentUnitPreferences,
			 permission=nauth.ACT_UPDATE,
			 request_method='PUT')
class _ContentUnitPreferencesPutView(AbstractAuthenticatedView,
									 ModeledContentUploadRequestUtilsMixin):

	def _transformInput(self, value):
		return value

	def updateContentObject(self, unit_prefs, externalValue, set_id=False, notify=True):
		# At this time, externalValue must be a dict containing the 'sharedWith' setting
		try:
			unit_prefs.sharedWith = externalValue['sharedWith']
			unit_prefs.lastModified = time.time()
			return unit_prefs
		except KeyError:
			exc_info = sys.exc_info()
			raise hexc.HTTPUnprocessableEntity, exc_info[1], exc_info[2]

	def __call__(self):
		value = self.readInput()
		self.updateContentObject(self.request.context, value)

		# Since we are used as a field updater, we want to return
		# the object whose field we updated (as is the general rule)
		# Recall that the root is special cased as ''

		ntiid = self.request.context.__parent__.__name__ or ntiids.ROOT
		if ntiid == ntiids.ROOT:
			# NOTE: This means that we are passing the wrong type of
			# context object
			self.request.view_name = ntiids.ROOT
			return _RootLibraryTOCRedirectView(self.request)

		content_lib = component.getUtility(IContentPackageLibrary)

		content_units = content_lib.pathToNTIID(ntiid)
		self.request.context = content_units[-1]
		return _LibraryTOCRedirectView(self.request)
