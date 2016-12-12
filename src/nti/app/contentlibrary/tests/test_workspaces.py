#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
does_not = is_not

import os
import shutil
import tempfile
import pyramid.interfaces

from zope import component
from zope import interface

from nti.appserver import pyramid_authorization

from nti.appserver.workspaces.interfaces import IWorkspace

from nti.contentlibrary.filesystem import DynamicFilesystemLibrary as DynamicLibrary

from nti.dataserver import interfaces as nti_interfaces

from nti.externalization import interfaces as ext_interfaces
from nti.externalization.externalization import toExternalObject

from nti.app.testing.layers import NewRequestLayerTest

class TestLibraryCollectionDetailExternalizer(NewRequestLayerTest):

	def setUp(self):
		super(TestLibraryCollectionDetailExternalizer, self).setUp()
		self.__policy = component.queryUtility(pyramid.interfaces.IAuthenticationPolicy)
		self.__acl_policy = component.queryUtility(pyramid.interfaces.IAuthorizationPolicy)

		self.temp_dir = tempfile.mkdtemp()
		self.entry_dir = os.path.join(self.temp_dir, 'TheEntry')
		os.mkdir(self.entry_dir)
		with open(os.path.join(self.entry_dir, 'eclipse-toc.xml'), 'w') as f:
			f.write("""<?xml version="1.0"?>
			<toc NTIRelativeScrollHeight="58" href="index.html"
			icon="icons/Faa%20Aviation%20Maintenance%20Technician%20Knowledge%20Test%20Guide-Icon.png"
			label="FAA Aviation Maintenance Technician Knowledge Test" ntiid="tag:nextthought.com,2011-10:foo-bar-baz" thumbnail="./thumbnails/index.png">
			<topic label="C1" href="faa-index.html" ntiid="tag:nextthought.com,2011-10:foo-bar-baz.child"/>
			</toc>""")
		self.library = DynamicLibrary(self.temp_dir)
		self.library.syncContentPackages()

		class Policy(object):
			interface.implements(pyramid.interfaces.IAuthenticationPolicy)
			def authenticated_userid(self, request):
				return 'jason.madden@nextthought.com'
			def effective_principals(self, request):
				result = [nti_interfaces.IPrincipal(x) for x in [self.authenticated_userid(request),
																 nti_interfaces.AUTHENTICATED_GROUP_NAME,
																 nti_interfaces.EVERYONE_GROUP_NAME]]
				return frozenset(result)

		self.policy = Policy()
		component.provideUtility(self.policy)
		self.acl_policy = pyramid_authorization.ZopeACLAuthorizationPolicy()
		component.provideUtility(self.acl_policy)

		self.library_workspace = component.getMultiAdapter((self.library, self.request), IWorkspace)
		self.library_collection = self.library_workspace.collections[0]

	def tearDown(self):
		shutil.rmtree(self.temp_dir)
		component.getGlobalSiteManager().unregisterUtility(self.policy)
		component.getGlobalSiteManager().unregisterUtility(self.acl_policy)
		if self.__policy:
			component.provideUtility(self.__policy)
		if self.__acl_policy:
			component.provideUtility(self.__acl_policy)
		super(TestLibraryCollectionDetailExternalizer, self).tearDown()

	def test_no_acl_file(self):
		external = ext_interfaces.IExternalObject(self.library_collection).toExternalObject()
		assert_that(external, has_entry('titles', has_length(1)))

	def test_malformed_acl_file_denies_all(self):
		with open(os.path.join(self.entry_dir, '.nti_acl'), 'w') as f:
			f.write("This file is invalid")
		external = ext_interfaces.IExternalObject(self.library_collection).toExternalObject()
		assert_that(external, has_entry('titles', has_length(0)))

	def test_specific_acl_file_forbids(self):
		acl_file = os.path.join(self.entry_dir, '.nti_acl')
		with open(acl_file, 'w') as f:
			f.write("Allow:User:[nti.actions.create]\n")
			f.write('Deny:system.Everyone:All\n')

		external = toExternalObject(self.library_collection)
		assert_that(external, has_entry('titles', has_length(0)))

	def test_specific_acl_to_user(self):
		acl_file = os.path.join(self.entry_dir, '.nti_acl')

		# Now, grant it to a user
		with open(acl_file, 'w') as f:
			f.write("Allow:jason.madden@nextthought.com:[zope.View]\n")

		external = toExternalObject(self.library_collection)
		assert_that(external, has_entry('titles', has_length(1)))

	def test_specific_acl_to_user_chapter(self):
		acl_file = os.path.join(self.entry_dir, '.nti_acl')

		# Back to the original entry on the ACL, denying it to everyone
		with open(acl_file, 'w') as f:
			f.write("Allow:User:[nti.actions.create]\n")
			f.write('Deny:system.Everyone:All\n')

		# But the first chapter is allowed to the user:
		with open(acl_file + '.1', 'w') as f:
			f.write("Allow:jason.madden@nextthought.com:[zope.View]\n")

		external = toExternalObject(self.library_collection)
		assert_that(external, has_entry('titles', has_length(1)))
