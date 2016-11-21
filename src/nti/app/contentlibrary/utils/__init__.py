#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IGlobalContentPackage
from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.mimetype.mimetype import nti_mimetype_with_class

from nti.ntiids.ntiids import find_object_with_ntiid

PAGE_INFO_MT = nti_mimetype_with_class('pageinfo')
PAGE_INFO_MT_JSON = PAGE_INFO_MT + '+json'

def _encode(s):
	return s.encode('utf-8') if isinstance(s, unicode) else s

def find_page_info_view_helper(request, page_ntiid_or_content_unit):
	"""
	Helper function to resolve a NTIID to PageInfo.
	"""

	# XXX Assuming one location in the hierarchy, plus assuming things
	# about the filename For the sake of the application (trello #932
	# https://trello.com/c/5cxwEgVH), if the question is nested in a
	# sub-section of a content library, we want to return the PageInfo
	# for the nearest containing *physical* file. In short, this means
	# we look for an href that does not have a '#' in it.
	if not IContentUnit.providedBy(page_ntiid_or_content_unit):
		content_unit = find_object_with_ntiid(page_ntiid_or_content_unit)
	else:
		content_unit = page_ntiid_or_content_unit

	while content_unit and '#' in getattr(content_unit, 'href', ''):
		content_unit = getattr(content_unit, '__parent__', None)

	page_ntiid = u''
	if content_unit:
		page_ntiid = content_unit.ntiid
	elif isinstance(page_ntiid_or_content_unit, basestring):
		page_ntiid = page_ntiid_or_content_unit

	# Rather than redirecting to the canonical URL for the page, request it
	# directly. This saves a round trip, and is more compatible with broken clients that
	# don't follow redirects parts of the request should be native strings,
	# which under py2 are bytes. Also make sure we pass any params to subrequest
	path = b'/dataserver2/Objects/' + _encode(page_ntiid)
	if request.query_string:
		path += '?' + _encode(request.query_string)

	# set subrequest
	subrequest = request.blank(path)
	subrequest.method = b'GET'
	subrequest.possible_site_names = request.possible_site_names
	# prepare environ
	subrequest.environ[b'REMOTE_USER'] = request.environ['REMOTE_USER']
	subrequest.environ[b'repoze.who.identity'] = request.environ['repoze.who.identity'].copy()
	for k in request.environ:
		if k.startswith('paste.') or k.startswith('HTTP_'):
			if k not in subrequest.environ:
				subrequest.environ[k] = request.environ[k]
	subrequest.accept = PAGE_INFO_MT_JSON

	# invoke
	result = request.invoke_subrequest(subrequest)
	return result

def yield_sync_content_packages(ntiids=()):
	library = component.getUtility(IContentPackageLibrary)
	if not ntiids:
		for package in library.contentPackages:
			if not IGlobalContentPackage.providedBy(package):
				yield package
	else:
		for ntiid in ntiids:
			obj = find_object_with_ntiid(ntiid)
			package = IContentPackage(obj, None)
			if package is None:
				logger.error("Could not find package with NTIID %s", ntiid)
			elif not IGlobalContentPackage.providedBy(package):
				yield package
yield_content_packages = yield_sync_content_packages
