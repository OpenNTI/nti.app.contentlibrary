#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import assert_that
from hamcrest.core.base_matcher import BaseMatcher

import os
import shutil
import tempfile

from zope import component

try:
	from nti.appserver.pyramid_authorization import ZopeACLAuthorizationPolicy as ACLAuthorizationPolicy
except ImportError:
	from pyramid.authorization import ACLAuthorizationPolicy

from nti.contentlibrary.contentunit import _clear_caches

from nti.contentlibrary.filesystem import FilesystemContentUnit
from nti.contentlibrary.filesystem import FilesystemContentPackage

from nti.dataserver import authorization as auth

from nti.dataserver import interfaces as nti_interfaces

from nti.app.contentlibrary.tests import ContentLibraryApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

class TestLibraryEntryAclProvider(ApplicationLayerTest):

	layer = ContentLibraryApplicationTestLayer

	@classmethod
	def setUpClass(cls):
		super(TestLibraryEntryAclProvider, cls).setUpClass()
		cls.temp_dir = tempfile.mkdtemp()
		cls.library_entry = FilesystemContentPackage()
		class Key(object):
			absolute_path = None
			bucket = None
			def __init__(self, bucket=None, name=None):
				self.absolute_path = name

			def readContents(self):
				try:
					with open(self.absolute_path, 'rb') as f:
						return f.read()
				except IOError:
					return None
		cls.library_entry.key = Key(name=os.path.join(cls.temp_dir, 'index.html'))
		cls.library_entry.children = []
		cls.library_entry.make_sibling_key = lambda k: Key(name=os.path.join(cls.temp_dir, k))

		child = FilesystemContentUnit()
		child.key = Key(name=os.path.join(cls.temp_dir, 'child.html'))
		child.make_sibling_key = lambda k: Key(name=os.path.join(cls.temp_dir, k))
		child.__parent__ = cls.library_entry
		child.ordinal = 1
		cls.library_entry.children.append(child)

		cls.acl_path = os.path.join(cls.temp_dir, '.nti_acl')
		component.provideUtility(ACLAuthorizationPolicy())

	@classmethod
	def tearDownClass(cls):
		shutil.rmtree(cls.temp_dir)
		super(TestLibraryEntryAclProvider, cls).tearDownClass()

	def setUp(self):
		super(TestLibraryEntryAclProvider, self).setUp()
		# Our use of a layer prevents our setUpClass from running
		if not hasattr(self, 'library_entry'):
			self.setUpClass()

		self.library_entry.ntiid = None
		try:
			os.unlink(self.acl_path)
		except OSError:
			pass

	def test_no_acl_file(self):
		acl_prov = nti_interfaces.IACLProvider(self.library_entry)
		assert_that(acl_prov, permits(nti_interfaces.AUTHENTICATED_GROUP_NAME,
									  auth.ACT_READ))

	def test_malformed_acl_file_denies_all(self):
		with open(self.acl_path, 'w') as f:
			f.write("This file is invalid")
		acl_prov = nti_interfaces.IACLProvider(self.library_entry)
		assert_that(acl_prov, denies(nti_interfaces.AUTHENTICATED_GROUP_NAME,
									 auth.ACT_READ))

	def test_specific_acl_file(self):
		with open(self.acl_path, 'w') as f:
			f.write("Allow:User:[nti.actions.create]\n")
			f.write(" # This line has a comment\n")
			f.write("  \n")  # This line is blank
			f.flush()

		for context in self.library_entry, self.library_entry.children[0]:
			__traceback_info__ = context
			acl_prov = nti_interfaces.IACLProvider(context)
			assert_that(acl_prov, permits("User", auth.ACT_CREATE))
			assert_that(acl_prov, denies("OtherUser", auth.ACT_CREATE))

		# Now, with an NTIID
		self.library_entry.ntiid = 'tag:nextthought.com,2011-10:PRMIA-HTML-Volume_III.A.2_converted.the_prm_handbook_volume_iii'
		acl_prov = nti_interfaces.IACLProvider(self.library_entry)
		assert_that(acl_prov, permits("User", auth.ACT_CREATE))
		assert_that(acl_prov, denies("OtherUser", auth.ACT_CREATE))

		assert_that(acl_prov, permits("content-role:prmia:Volume_III.A.2_converted.the_prm_handbook_volume_iii".lower(), auth.ACT_READ))
		assert_that(acl_prov, permits(nti_interfaces.IGroup("content-role:prmia:Volume_III.A.2_converted.the_prm_handbook_volume_iii".lower()), auth.ACT_READ))

		# Now I can write another user in for access to just the child entry
		with open(self.acl_path + '.1', 'w') as f:
			f.write('Allow:OtherUser:All\n')
		_clear_caches()

		# Nothing changed an the top level
		context = self.library_entry
		acl_prov = nti_interfaces.IACLProvider(context)
		assert_that(acl_prov, permits("User", auth.ACT_CREATE))
		assert_that(acl_prov, denies("OtherUser", auth.ACT_CREATE))

		# But the child level now allows access
		context = self.library_entry.children[0]
		acl_prov = nti_interfaces.IACLProvider(context)
		assert_that(acl_prov, permits("User", auth.ACT_CREATE))
		assert_that(acl_prov, permits("OtherUser", auth.ACT_CREATE))

		# The same applies if it is at the 'default' location
		os.rename(self.acl_path + '.1', self.acl_path + '.default')
		acl_prov = nti_interfaces.IACLProvider(context)
		assert_that(acl_prov, permits("User", auth.ACT_CREATE))
		assert_that(acl_prov, permits("OtherUser", auth.ACT_CREATE))

from zope.security.permission import Permission

class Permits(BaseMatcher):

	def __init__(self, prin, perm, policy=ACLAuthorizationPolicy()):
		super(Permits, self).__init__()
		try:
			self.prin = (nti_interfaces.IPrincipal(prin),)
		except TypeError:
			self.prin = prin
		self.perm = perm if nti_interfaces.IPermission.providedBy(perm) else Permission(perm)
		self.policy = policy

	def _matches(self, item):
		if not hasattr(item, '__acl__'):
			item = nti_interfaces.IACLProvider(item, item)
		return self.policy.permits(item,
									self.prin,
									self.perm)

	__description__ = 'ACL permitting '
	def describe_to(self, description):
		description.append_text(self.__description__) \
								 .append_text(','.join([x.id for x in self.prin])) \
								 .append_text(' permission ') \
								 .append(self.perm.id)

	def describe_mismatch(self, item, mismatch_description):
		acl = getattr(item, '__acl__', None)
		if acl is None:
			acl = getattr(nti_interfaces.IACLProvider(item, item), '__acl__', None)

		mismatch_description.append_text('was ').append_description_of(item)
		if acl is not None and acl is not item:
			mismatch_description.append_text(' with acl ').append_description_of(acl)

class Denies(Permits):

	__description__ = 'ACL denying'

	def _matches(self, item):
		return not super(Denies, self)._matches(item)

def permits(prin, perm):
	return Permits(prin, perm)

def denies(prin, perm):
	return Denies(prin, perm)
