#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: too many ancestors
# pylint: disable=I0011,R0901

# If passing strings, they require bytes, NOT unicode, or they fail
from zope.container.constraints import contains
from zope.container.constraints import containers

from zope.securitypolicy.interfaces import IRolePermissionManager

# Content-specific boards and forums
# We define these as a distinct set of classes/interfaces/mimetypes/ntiids
# so that things like analytics and notable data can distinguish them.
# They are otherwise expected to be modeled exactly the same as community boards.

from nti.dataserver.contenttypes.forums.interfaces import IGeneralForum
from nti.dataserver.contenttypes.forums.interfaces import IUseOIDForNTIID
from nti.dataserver.contenttypes.forums.interfaces import IPublishableTopic
from nti.dataserver.contenttypes.forums.interfaces import IDefaultForumBoard
from nti.dataserver.contenttypes.forums.interfaces import IGeneralForumComment
from nti.dataserver.contenttypes.forums.interfaces import IGeneralHeadlinePost
from nti.dataserver.contenttypes.forums.interfaces import IGeneralHeadlineTopic

from nti.dataserver.interfaces import IShouldHaveTraversablePath

from nti.schema.field import List
from nti.schema.field import Object

class IContentBoard(IDefaultForumBoard,
					IShouldHaveTraversablePath,
					IUseOIDForNTIID):
	"""
	A board belonging to a particular piece of content.
	"""
	contains(b'.IContentForum')
	__setitem__.__doc__ = None

class IContentForum(IGeneralForum,
					IShouldHaveTraversablePath):
	"""
	A forum belonging to a particular piece of content.
	"""
	containers(IContentBoard)
	contains(b'.IContentHeadlineTopic')
	__parent__.required = False

class IContentHeadlinePost(IGeneralHeadlinePost):
	"""The headline of a content topic"""
	containers(b'.IContentHeadlineTopic')
	__parent__.required = False

class IContentHeadlineTopic(IGeneralHeadlineTopic,
							IPublishableTopic):
	containers(IContentForum)
	contains(b'.IContentCommentPost')
	__parent__.required = False
	headline = Object(IContentHeadlinePost,
					  title="The main, first post of this topic.")

class IContentCommentPost(IGeneralForumComment):
	containers(IContentHeadlineTopic) # Adds __parent__ as required
	__parent__.required = False

# External client preferences

from zope.location.interfaces import ILocation

from dolmen.builtins import IUnicode

from nti.dataserver.interfaces import ILastModified

class IContentUnitPreferences(ILocation,
							  ILastModified):
	"""
	Storage location for preferences related to a content unit.
	"""
	# NOTE: This can actually be None in some cases, which makes it
	# impossible to validate this schema.
	sharedWith = List( value_type=Object(IUnicode),
					   title="List of usernames to share with" )

class IContentPackageRolePermissionManager(IRolePermissionManager):
	"""
	A role permission manager for ``IContentPackage``.
	"""

	def initialize():
		"""
		Initialize our role manager to default status.
		"""
