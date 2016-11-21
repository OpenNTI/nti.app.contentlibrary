#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

import gc

import os
import os.path

from zope import component
from zope import interface
from zope.location.interfaces import IRoot
from zope.traversing.interfaces import IEtcNamespace

from zope.site.folder import Folder
from zope.site.folder import rootFolder

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.app.testing.application_webtest import ApplicationTestLayer

from nti.contentlibrary.bundle import ContentPackageBundleLibrary
from nti.contentlibrary.interfaces import IContentPackageBundleLibrary
from nti.contentlibrary.interfaces import ISyncableContentPackageBundleLibrary
from nti.contentlibrary.filesystem import EnumerateOnceFilesystemLibrary as FileLibrary

from nti.dataserver.interfaces import IDataserver

from nti.dataserver.tests.mock_dataserver import mock_db_trans

class _SharedSetup(object):

	@staticmethod
	def _setup_library(layer, *args, **kwargs ):
		return FileLibrary(layer.library_dir)

	@staticmethod
	def install_bundles(layer, ds):
		# XXX: This duplicates a lot of what's done by subscribers
		# in nti.contentlibrary
		with mock_db_trans(ds):

			ds = ds.dataserver_folder

			global_bundle_library = ContentPackageBundleLibrary()
			layer.bundle_library = global_bundle_library
			ds.getSiteManager().registerUtility(global_bundle_library, IContentPackageBundleLibrary)
			# For traversal purposes (for now) we put the library in '/dataserver2/++etc++bundles/bundles'
			site = Folder()
			ds['++etc++bundles'] = site
			site['bundles'] = global_bundle_library

			bucket = layer.global_library._enumeration.root.getChildNamed('sites').getChildNamed('localsite').getChildNamed('ContentPackageBundles')
			ISyncableContentPackageBundleLibrary(global_bundle_library).syncFromBucket(bucket)

			ds.getSiteManager().registerUtility(site, provided=IEtcNamespace, name='bundles')

	@staticmethod
	def setUp(layer):
		# Must implement!
		gsm = component.getGlobalSiteManager()
		layer._old_library = gsm.queryUtility(IContentPackageLibrary)
		if layer._old_library is None:
			print("WARNING: A previous layer removed the global IContentPackageLibrary", layer)

		global_library = layer.global_library = layer._setup_library()

		gsm.registerUtility(global_library, IContentPackageLibrary)
		global_library.syncContentPackages()

	@staticmethod
	def tearDown(layer):
		# Must implement!
		# Use the dict to avoid inheritance
		new_library = layer.__dict__['global_library']
		old_library = layer.__dict__['_old_library']
		component.getGlobalSiteManager().unregisterUtility(new_library, IContentPackageLibrary)
		if old_library is not None:
			component.getGlobalSiteManager().registerUtility(old_library, IContentPackageLibrary)
		else:
			print("WARNING: when tearing down layer", layer, "no previous library to restore")
		del layer.global_library
		del layer._old_library
		gc.collect()

class CourseTestContentApplicationTestLayer(ApplicationTestLayer):

	library_dir = os.path.join( os.path.dirname(__file__), 'library' )

	@classmethod
	def _setup_library( cls, *args, **kwargs ):
		return _SharedSetup._setup_library(cls)

	@classmethod
	def setUp(cls):
		# Must implement!
		_SharedSetup.setUp(cls)

	@classmethod
	def tearDown(cls):
		_SharedSetup.tearDown(cls)
		# Must implement!

	@classmethod
	def testSetUp(cls, test=None):
		test = test or find_test()
		test.setUpDs = lambda *args: _SharedSetup.install_bundles(cls, *args)

	@classmethod
	def testTearDown(cls, test=None):
		pass

	# TODO: May need to recreate the application with this library?

import nti.contentlibrary.tests
from nti.testing.layers import find_test

class ContentLibraryApplicationTestLayer(ApplicationTestLayer):
	library_dir = os.path.join( os.path.dirname(nti.contentlibrary.tests.__file__) )
	@classmethod
	def _setup_library( cls, *args, **kwargs ):
		return _SharedSetup._setup_library(cls)

	@classmethod
	def setUp(cls):
		# Must implement!
		_SharedSetup.setUp(cls)

	@classmethod
	def tearDown(cls):
		_SharedSetup.tearDown(cls)
		# Must implement!

	@classmethod
	def testSetUp(cls, test=None):
		test = test or find_test()
		test.setUpDs = lambda ds: _SharedSetup.install_bundles(cls, ds)

	@classmethod
	def testTearDown(cls, test=None):
		pass

	# TODO: May need to recreate the application with this library?
