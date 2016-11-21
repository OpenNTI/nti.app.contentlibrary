#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from zope.location.interfaces import LocationError

from zope.traversing.interfaces import ITraversable

from pyramid import traversal

from pyramid.threadlocal import get_current_request

from nti.dataserver import users
from nti.dataserver import authorization_acl as nacl

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import ALL_PERMISSIONS
from nti.dataserver.interfaces import ACLLocationProxy

from nti.ntiids import ntiids

from .interfaces import IContentUnitPreferences

def _with_acl(prefs):
	"""
	Proxies the preferences object to have an ACL
	that allows only its owner to make changes.
	"""
	user = traversal.find_interface(prefs, IUser)
	if user is None:  # pragma: no cover
		return prefs
	# TODO: Replace this with a real ACL provider
	return ACLLocationProxy(
					prefs,
					prefs.__parent__,
					prefs.__name__,
					nacl.acl_from_aces(nacl.ace_allowing(user.username,
														 ALL_PERMISSIONS)))

@interface.implementer(ITraversable)
class _ContainerFieldsTraversable(object):
	"""
	An :class:`zope.traversing.interfaces.ITraversable` for the
	updateable fields of a container.

	Register as a namespace traverser for the ``fields`` namespace.

	FIXME: This is registered for
	:class:`nti.containers.containers.LastModifiedBTreeContainer`. It
	needs to be handled at an interface level, not this class level.
	The intent is to adapt to the UGD containers found in a User, but
	this also catches forum containers and who knows what all else.
	The impact is limited though because it is registered in the fields namespace.
	"""

	def __init__(self, context, request=None):
		self.context = context

	def traverse(self, name, remaining_path):
		if name != 'sharingPreference':  # pragma: no cover
			raise LocationError(name)
		return _with_acl(IContentUnitPreferences(self.context))

@interface.implementer(ITraversable)
class _ContentUnitFieldsTraversable(object):
	"""
	An :class:`zope.traversing.interfaces.ITraversable` for the
	preferences stored on a :class:`nti.contentlibrary.interfaces.IContentUnit`.

	Register as a namespace traverser for the ``fields`` namespace
	"""

	def __init__(self, context, request=None):
		self.context = context
		self.request = request

	def traverse(self, name, remaining_path):
		if name != 'sharingPreference':  # pragma: no cover
			raise LocationError(name)

		request = self.request or get_current_request()
		remote_user = users.User.get_user(request.authenticated_userid,
										  dataserver=request.registry.getUtility(IDataserver))
		# Preferences for the root are actually stored
		# on the unnamed node
		ntiid = '' if self.context.ntiid == ntiids.ROOT else self.context.ntiid
		container = remote_user.getContainer(ntiid)
		# If we are expecting to write preferences, make sure the
		# container exists, even if it hasn't been used
		if container is None and self.request and self.request.method == 'PUT':
			container = remote_user.containers.getOrCreateContainer(ntiid)
		return _with_acl(IContentUnitPreferences(container))
