#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Implements :mod:`nti.contentprocessing.metadata_extractors` related
functionality for items in the content library.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentUnitHrefMapper

from nti.contentprocessing.interfaces import IContentMetadata

from nti.contentprocessing.metadata_extractors import ImageMetadata
from nti.contentprocessing.metadata_extractors import ContentMetadata

@component.adapter(IContentUnit)
@interface.implementer(IContentMetadata)
def ContentMetadataFromContentUnit(content_unit):
	# TODO: Is this the right level at which to externalize the hrefs?
	result = ContentMetadata(title=content_unit.title,
							 description=content_unit.description,
							 contentLocation=IContentUnitHrefMapper(content_unit).href,
							 mimeType='text/html')
	result.__name__ = '@@metadata'
	result.__parent__ = content_unit  # for ACL

	def _attach_image(key):
		image = ImageMetadata(url=IContentUnitHrefMapper(key).href)
		image.__parent__ = result
		if not result.images:
			result.images = []
		result.images.append(image)

	for name in ('icon', 'thumbnail'):
		key = getattr(content_unit, name)
		if key:
			_attach_image(key)
	return result
