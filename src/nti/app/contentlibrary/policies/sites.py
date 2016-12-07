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

from nti.appserver.policies.site_policies import get_possible_site_names

from nti.contentlibrary.interfaces import IS3Key
from nti.contentlibrary.interfaces import IAbsoluteContentUnitHrefMapper

@component.adapter(IS3Key)
@interface.implementer(IAbsoluteContentUnitHrefMapper)
class RequestAwareS3KeyHrefMapper(object):
	"""
	Produces HTTP URLs for keys in buckets.	Takes steps to work with CORS
	and other distribution strategies.

	Use this mapper when the bucket name is a DNS name, and the bucket name
	also has a DNS CNAME set up for it, and the application accessing the content
	was served from the same CNAME origin (or doesn't care about cross-origin concerns).
	"""
	href = None

	def __init__(self, key):
		# TODO: The following may not be the case?
		# We have to force HTTP here, because using https (or protocol relative)
		# falls down for the browser: the certs on the CNAME we redirect to, *.s3.aws.amazon.com
		# don't match for bucket.name host
		sites = get_possible_site_names()
		if sites:
			# In the CORS case, we may be coming from an origin, to the dataserver
			# and serving content which ought to come back from the origin CDN. We cannot use
			# the request.host (Host) header, because that would name the dataserver, which
			# might not be the content origin. The preferred sites send back the
			# origin first
			self.href = 'http://' + sites[0] + '/' + key.key
		else:
			self.href = 'http://' + key.bucket.name + '/' + key.key
