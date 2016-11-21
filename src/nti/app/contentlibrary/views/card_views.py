#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views related to cards in content.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import pyquery

from zope import component
from zope import interface

from zope.container.contained import Contained

from pyramid.view import view_config
from pyramid import httpexceptions as hexc

from nti.app.contentlibrary import PAGE_INFO_MT_JSON

from nti.app.contentlibrary.views.library_views import find_page_info_view_helper

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.dataserver import authorization as nauth

from nti.ntiids.interfaces import INTIIDResolver

# re-export
PAGE_INFO_MT_JSON = PAGE_INFO_MT_JSON

# See also assessment_views, especially for notes on Accept header handling.

# Content cards are not true modeled content; this package
# contains traversal helpers to fake it
class _ContentCard(Contained):

	__slots__ = (b'path', b'ntiid')

	def __init__(self, path):
		self.path = path

	@property
	def ntiid(self):
		return None

@interface.implementer(INTIIDResolver)
class _ContentCardResolver(object):
	"""
	Provisional resolver for cards in content.
	"""
	def resolve(self, key):
		library = component.queryUtility(IContentPackageLibrary)
		paths = library.pathsToEmbeddedNTIID(key) if library else None
		if paths:
			# We arbitrarily choose the first one.
			# We might instead want to go through and find one that
			# is accessible for the current user?
			card = _ContentCard(paths[0])
			# Preserve the parent for ACL purposes
			card.__parent__ = paths[0][-1]
			card.__name__ = key
			return card

_view_defaults = dict(route_name='objects.generic.traversal',
					  renderer='rest',
					  context=_ContentCard,
					  permission=nauth.ACT_READ,
					  request_method='GET')
@view_config(accept=PAGE_INFO_MT_JSON.encode('ascii'), **_view_defaults)
def pageinfo_from_content_card_view(request):
	assert request.accept
	return find_page_info_view_helper(request, request.context.path[-1])

@view_config(accept=b'application/vnd.nextthought.link+json', **_view_defaults)
def get_card_view_link(request):
	# Not supported.
	return hexc.HTTPBadRequest()

# explicit empty accept, else we get a ConfigurationConflict and/or
# no-Accept header goes to the wrong place
@view_config(accept=b'', **_view_defaults)
@view_config(**_view_defaults)
def get_card_view(request):
	# NOTE: These are not modeled content. What we are returning is arbitrary
	# and WILL change.

	containing_unit = request.context.path[-1]
	contents = None  # Walk up to find physical contents
	while containing_unit is not None and not contents:
		contents = containing_unit.read_contents()
		containing_unit = getattr(containing_unit, '__parent__', None)

	if not contents:
		return hexc.HTTPNotFound()

	pq = pyquery.PyQuery(contents, parser='html')

	# Because of syntax issues, and unicode issues, we have to iterate
	# for the object ourself

	nodes = pq(b'object[data-ntiid]')
	object_elm = None
	for node in nodes:
		if 	node.tag == 'object' and \
			node.attrib.get('data-ntiid') == request.context.__name__:
			object_elm = node
			break

	if object_elm is None:
		return hexc.HTTPNotFound()

	result = {}
	for k, v in object_elm.attrib.items():
		if k == 'class':  # CSS class
			continue
		if k == 'type':
			k = 'MimeType'

		if k.startswith('data-'):
			k = k[5:]
		if k == 'ntiid':
			k = 'NTIID'
		result[k] = v

	img = object_elm.find('img')
	if img is not None:
		result['image'] = img.attrib['src']

	if 'description' not in result:
		result['description'] = object_elm.text_content().strip()
	return result

del _view_defaults
