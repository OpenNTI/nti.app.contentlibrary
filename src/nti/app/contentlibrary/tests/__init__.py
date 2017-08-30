#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

import gc

import os
import os.path

from zope import component
from zope import interface

from zope.location.interfaces import IRoot

from zope.site.folder import Folder
from zope.site.folder import rootFolder

import ZODB

from zope.traversing.interfaces import IEtcNamespace

from nti.contentlibrary.bundle import ContentPackageBundleLibrary

from nti.contentlibrary.filesystem import EnumerateOnceFilesystemLibrary as FileLibrary

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IContentPackageBundleLibrary
from nti.contentlibrary.interfaces import ISyncableContentPackageBundleLibrary

from nti.dataserver.interfaces import IDataserver

from nti.site.hostpolicy import run_job_in_all_host_sites

from nti.app.testing.application_webtest import ApplicationTestLayer

from nti.dataserver.tests.mock_dataserver import WithMockDS
from nti.dataserver.tests.mock_dataserver import mock_db_trans
from nti.dataserver.tests.mock_dataserver import DSInjectorMixin

from nti.testing.layers import find_test
from nti.testing.layers import GCLayerMixin
from nti.testing.layers import ZopeComponentLayer
from nti.testing.layers import ConfiguringLayerMixin

import zope.testing.cleanup


class SharedConfiguringTestLayer(ZopeComponentLayer,
                                 GCLayerMixin,
                                 ConfiguringLayerMixin,
                                 DSInjectorMixin):

    set_up_packages = ('nti.dataserver', 'nti.app.contentlibrary')

    @classmethod
    def setUp(cls):
        cls.setUpPackages()

    @classmethod
    def tearDown(cls):
        cls.tearDownPackages()
        zope.testing.cleanup.cleanUp()

    @classmethod
    def testSetUp(cls, test=None):
        cls.setUpTestDS(test)

    @classmethod
    def testTearDown(cls):
        pass


class _SharedSetup(object):

    @staticmethod
    def _setup_library(layer, *unused_args, **unused_kwargs):
        return FileLibrary(layer.library_dir)

    @staticmethod
    def install_bundles(layer, ds):
        # XXX: This duplicates a lot of what's done by subscribers
        # in nti.contentlibrary
        with mock_db_trans(ds):

            ds = ds.dataserver_folder

            global_bundle_library = ContentPackageBundleLibrary()
            layer.bundle_library = global_bundle_library
            ds.getSiteManager().registerUtility(global_bundle_library,
                                                IContentPackageBundleLibrary)
            # For traversal purposes (for now) we put the library in
            # '/dataserver2/++etc++bundles/bundles'
            site = Folder()
            ds['++etc++bundles'] = site
            site['bundles'] = global_bundle_library

            root = layer.global_library._enumeration.root
            bucket = root.getChildNamed('sites').getChildNamed('localsite').getChildNamed('ContentPackageBundles')

            ISyncableContentPackageBundleLibrary(global_bundle_library).syncFromBucket(bucket)

            ds.getSiteManager().registerUtility(site,
                                                provided=IEtcNamespace,
                                                name='bundles')

    @staticmethod
    def setUp(layer):
        # Must implement!
        gsm = component.getGlobalSiteManager()
        layer._old_library = gsm.queryUtility(IContentPackageLibrary)
        if layer._old_library is None:
            print("WARNING: A previous layer removed the global IContentPackageLibrary",
                  layer)

        global_library = layer.global_library = layer._setup_library()

        gsm.registerUtility(global_library, IContentPackageLibrary)
        global_library.syncContentPackages()

    @staticmethod
    def tearDown(layer):
        # Must implement!
        # Use the dict to avoid inheritance
        new_library = layer.__dict__['global_library']
        old_library = layer.__dict__['_old_library']
        component.getGlobalSiteManager().unregisterUtility(new_library,
                                                           IContentPackageLibrary)
        if old_library is not None:
            component.getGlobalSiteManager().registerUtility(old_library,
                                                             IContentPackageLibrary)
        else:
            print("WARNING: when tearing down layer",
                  layer,
                  "no previous library to restore")
        del layer.global_library
        del layer._old_library
        gc.collect()


class CourseTestContentApplicationTestLayer(ApplicationTestLayer):

    library_dir = os.path.join(os.path.dirname(__file__), 'library')

    @classmethod
    def _setup_library(cls, *unused_args, **unused_kwargs):
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


class ContentLibraryApplicationTestLayer(ApplicationTestLayer):

    library_dir = os.path.join(os.path.dirname(nti.contentlibrary.tests.__file__))

    @classmethod
    def _setup_library(cls, *unused_args, **unused_kwargs):
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


class ExLibraryApplicationTestLayer(ApplicationTestLayer):

    library_dir = os.path.join(os.path.dirname(__file__), 'ExLibrary')

    @classmethod
    def _setup_library(cls, *unused_args, **unused_kwargs):
        return FileLibrary(cls.library_dir)

    @classmethod
    def setUp(cls):
        # Must implement!
        gsm = component.getGlobalSiteManager()
        cls.__old_library = gsm.queryUtility(IContentPackageLibrary)
        if cls.__old_library is not None:
            cls.__old_library.resetContentPackages()

        lib = cls._setup_library()

        gsm.registerUtility(lib, IContentPackageLibrary)
        lib.syncContentPackages()
        cls.__current_library = lib

    @classmethod
    def tearDown(cls):
        # Must implement!
        gsm = component.getGlobalSiteManager()
        cls.__current_library.resetContentPackages()
        gsm.unregisterUtility(cls.__current_library, IContentPackageLibrary)
        del cls.__current_library
        if cls.__old_library is not None:
            gsm.registerUtility(cls.__old_library, IContentPackageLibrary)
            # XXX Why would we need to sync the content packages here? It's been
            # sidelined this whole time. Doing so leads to InappropriateSiteError
            # cls.__old_library.syncContentPackages()

        del cls.__old_library
        gc.collect()

    # TODO: May need to recreate the application with this library?

    @classmethod
    def testSetUp(cls):
        # must implement!
        pass

    @classmethod
    def testTearDown(cls):
        # must implement!
        pass

# persistent site library


def load_global_library():
    lib = component.getGlobalSiteManager().queryUtility(IContentPackageLibrary)
    if lib is None:
        return
    try:
        del lib.contentPackages
    except AttributeError:
        pass
    lib.syncContentPackages()


def _do_then_enumerate_library(do=None, sync_libs=True):

    database = ZODB.DB(ApplicationTestLayer._storage_base,
                       database_name='Users')

    @WithMockDS(database=database)
    def _create():
        with mock_db_trans():
            if do is not None:
                do()
            load_global_library()
            if sync_libs:
                from nti.app.contentlibrary.synchronize import syncContentPackages
                syncContentPackages()
    _create()


def _reset_site_libs():
    seen = []

    def d():
        lib = component.getUtility(IContentPackageLibrary)
        if lib in seen:
            return
        seen.append(lib)
        lib.resetContentPackages()

    from zope.component import hooks
    with hooks.site(None):
        d()
    run_job_in_all_host_sites(d)


class PersistentApplicationTestLayer(ApplicationTestLayer):

    _library_path = 'PersistentLibrary'
    _sites_names = ('platform.ou.edu',)

    library_path = os.path.join(os.path.dirname(__file__),
                                _library_path)

    @staticmethod
    def _setup_library(layer, *unused_args, **unused_kwargs):
        return FileLibrary(layer.library_path)

    @staticmethod
    def _install_library(layer, *args, **kwargs):
        gsm = component.getGlobalSiteManager()
        layer._old_library = gsm.queryUtility(IContentPackageLibrary)
        layer._new_library = layer._setup_library(layer, *args, **kwargs)
        gsm.registerUtility(layer._new_library, IContentPackageLibrary)
        _do_then_enumerate_library(*args, **kwargs)

    @staticmethod
    def _uninstall_library(layer):
        _reset_site_libs()
        # Bypass inheritance for these, make sure we're only getting from this
        # class.
        new_lib = layer.__dict__['_new_library']
        old_lib = layer.__dict__['_old_library']
        gsm = component.getGlobalSiteManager()
        gsm.unregisterUtility(new_lib, IContentPackageLibrary)
        if old_lib is not None:
            old_lib.resetContentPackages()
            gsm.registerUtility(old_lib, IContentPackageLibrary)
        del layer._old_library
        del layer._new_library
        gc.collect()

    @classmethod
    def setUp(cls):
        # Must implement!
        cls._install_library(cls)

    @classmethod
    def tearDown(cls):
        # Must implement!
        # Clean up any side effects of these content packages being
        # registered
        def cleanup():
            cls._uninstall_library(cls)

        _do_then_enumerate_library(cleanup, sync_libs=False)

    testSetUp = testTearDown = classmethod(lambda cls: None)
