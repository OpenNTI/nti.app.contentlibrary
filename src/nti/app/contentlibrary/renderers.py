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

from nti.app.contentlibrary.interfaces import IContentUnitInfo

from nti.app.renderers.interfaces import IPreRenderResponseCacheController

@component.adapter(IContentUnitInfo)
@interface.implementer(IPreRenderResponseCacheController)
class _ContentUnitInfoCacheController(object):
	# rendering this doesn't take long, and we need the rendering
	# process to decorate us with any sharing preferences that may change
	# and update our modification stamp (this is why we can't be a
	# subclass of _AbstractReliableLastModifiedCacheController)

	# We used to set a cache-contral max-age header of five minutes
	# because that sped up navigation in the app noticebly. But it
	# also led to testing problems if the tester switched accounts.
	# The fix is to have the app cache these objects itself,
	# and we go back to ETag/LastModified caching based on
	# the rendered form.
	# See Trell #2962 https://trello.com/c/1TGen4z1

	def __init__(self, context):
		pass

	def __call__(self, context, system):
		return system['request'].response
