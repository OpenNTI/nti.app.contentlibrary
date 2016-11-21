#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import random
import hashlib

from zope import component

from zope.component import hooks

from zope.traversing.interfaces import IEtcNamespace

from nti.app.authentication import get_remote_user

from nti.appserver.pyramid_authorization import is_readable

from nti.dataserver.interfaces import IMemcacheClient

from nti.property.property import Lazy

#: Default memcached expiration time in secs
EXP_TIME = 86400

def _memcached_client():
	return component.queryUtility(IMemcacheClient)

def _encode_keys(*keys):
	result = hashlib.md5()
	for value in keys:
		result.update(str(value).lower())
	return result.hexdigest()

def _last_synchronized():
	hostsites = component.queryUtility(IEtcNamespace, name='hostsites')
	result = getattr(hostsites, 'lastSynchronized', 0)
	return result or 0

def _get_user_ticket_key(user):
	result = '/contentlibrary/%s/ticket' % getattr(user, 'username', user)
	return result.lower()
	
def _get_user_ticket(user, client):
	try:
		if client != None:
			key = _get_user_ticket_key(user)
			result = client.get(key)
	except:
		result = None
	return result or 0

def _set_user_ticket(user, client):
	try:
		if client != None:
			key = _get_user_ticket_key(user)
			client.set(key, random.randint(0, 10000), time=EXP_TIME)
	except:
		pass

def _get_base_key(username, ntiid):
	cur_site = hooks.getSite()
	lastSync = _last_synchronized()
	result = _encode_keys(cur_site.__name__, username, ntiid, lastSync)
	return result
	
def _get_user_content_package_key(user, content_package, client):
	ticket = _get_user_ticket(user, client)
	base = _get_base_key(user.username, content_package.ntiid)
	result = "/contentlibrary/%s/%s" % (base, ticket)
	return result.lower()
	
class _PermissionedContentPackageMixin(object):

	@Lazy
	def _client(self):
		return _memcached_client()

	def _test_and_cache(self, content_package):
		# test readability
		request = self.request
		if is_readable(content_package, request):
			result = True
		else:
			# Nope. What about a top-level child? TODO: Why we check children?
			result = any((is_readable(x, request) for x in content_package.children))

		try:
			# cache if possible
			client = self._client
			user = get_remote_user()
			if client != None and user != None:
				key = _get_user_content_package_key(user, content_package, client)
				client.set(key, bool(result), time=EXP_TIME)
		except Exception as e:
			logger.error("Cannot set value(s) in memcached %s", e)
		return result

	def _test_is_readable(self, content_package):
		try:
			client = self._client
			user = get_remote_user()
			if client != None and user != None:
				key = _get_user_content_package_key(user, content_package, client)
				result = client.get(key)
				if result is not None:
					return result
		except Exception as e:
			logger.error("Cannot get value(s) from memcached %s", e)

		result = self._test_and_cache(content_package)
		return result
