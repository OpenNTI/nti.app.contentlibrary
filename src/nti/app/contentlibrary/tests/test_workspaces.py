#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

import fudge

from hamcrest import is_not
from hamcrest import contains
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
does_not = is_not

import os
import shutil
import tempfile

from zope import component
from zope import interface

from pyramid.interfaces import IAuthorizationPolicy
from pyramid.interfaces import IAuthenticationPolicy

from nti.app.contentlibrary.workspaces.adapters import BundleLibraryCollection
from nti.app.contentlibrary.workspaces.adapters import LibraryCollection

from nti.appserver.workspaces.interfaces import IWorkspace

from nti.appserver.pyramid_authorization import ZopeACLAuthorizationPolicy

from nti.contentlibrary.bundle import PublishableContentPackageBundle

from nti.contentlibrary.filesystem import DynamicFilesystemLibrary as DynamicLibrary

from nti.dataserver.interfaces import EVERYONE_GROUP_NAME
from nti.dataserver.interfaces import AUTHENTICATED_GROUP_NAME

from nti.dataserver.interfaces import IPrincipal

from nti.externalization.interfaces import IExternalObject

from nti.externalization.externalization import toExternalObject

from nti.app.testing.layers import NewRequestLayerTest


class TestLibraryCollectionDetailExternalizer(NewRequestLayerTest):

    def setUp(self):
        super(TestLibraryCollectionDetailExternalizer, self).setUp()
        self.__policy = component.queryUtility(IAuthenticationPolicy)
        self.__acl_policy = component.queryUtility(IAuthorizationPolicy)

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
            interface.implements(IAuthenticationPolicy)

            def authenticated_userid(self, unused_request):
                return 'jason.madden@nextthought.com'

            def effective_principals(self, request):
                result = [IPrincipal(x) for x in [self.authenticated_userid(request),
                                                  AUTHENTICATED_GROUP_NAME,
                                                  EVERYONE_GROUP_NAME]]
                return frozenset(result)

        self.policy = Policy()
        component.provideUtility(self.policy)
        self.acl_policy = ZopeACLAuthorizationPolicy()
        component.provideUtility(self.acl_policy)

        self.library_workspace = component.getMultiAdapter((self.library, self.request),
                                                           IWorkspace)
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
        external = IExternalObject(self.library_collection).toExternalObject()
        assert_that(external, has_entry('titles', has_length(1)))

    def test_malformed_acl_file_denies_all(self):
        with open(os.path.join(self.entry_dir, '.nti_acl'), 'w') as f:
            f.write("This file is invalid")
        external = IExternalObject(self.library_collection).toExternalObject()
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

class TestAdapters(NewRequestLayerTest):

    @fudge.patch("nti.app.contentlibrary.workspaces.adapters.get_current_request")
    def testBundleLibraryCollection(self, mock_current_request):
        mock_current_request.is_callable().returns(self.request)

        bundles = []
        for title, createdTime in ( (u'tiger', 20),
                                    (u'banana', 30),
                                    (u'bound ok', 40)):
            bundles.append(PublishableContentPackageBundle(title=title, createdTime=createdTime))

        lib = fudge.Fake('library').provides('getBundles').is_callable().returns([])
        col = BundleLibraryCollection(lib)
        assert_that(col.library_items, has_length(0))

        lib = fudge.Fake('library').provides('getBundles').is_callable().returns(bundles)
        col = BundleLibraryCollection(lib)
        # Default sort title
        assert_that([x.title for x in col.library_items], contains('banana', 'bound ok', 'tiger'))

        # Sorting
        params = self.request.params
        params['sortOn'] = 'title'
        params['sortOrder'] = 'ascending'

        col = BundleLibraryCollection(lib)
        assert_that([x.title for x in col.library_items], contains('banana', 'bound ok', 'tiger'))

        params['sortOn'] = 'title'
        params['sortOrder'] = 'descending'

        col = BundleLibraryCollection(lib)
        assert_that([x.title for x in col.library_items], contains('tiger', 'bound ok', 'banana'))

        params['sortOn'] = 'createdTime'
        params['sortOrder'] = 'ascending'

        col = BundleLibraryCollection(lib)
        assert_that([x.title for x in col.library_items], contains('tiger', 'banana', 'bound ok'))

        params['sortOn'] = 'createdTime'
        params['sortOrder'] = 'descending'

        col = BundleLibraryCollection(lib)
        assert_that([x.title for x in col.library_items], contains('bound ok', 'banana', 'tiger'))

        # Unknown sortOn
        params['sortOn'] = 'xxx_'
        col = BundleLibraryCollection(lib)
        assert_that([x.title for x in col.library_items], contains('tiger', 'banana', 'bound ok'))

        # Filter by prefix
        params['filter'] = 'ok'
        params['sortOn'] = 'createdTime'
        params['sortOrder'] = 'ascending'

        col = BundleLibraryCollection(lib)
        assert_that([x.title for x in col.library_items], contains('bound ok'))

        params['filter'] = 'b'
        col = BundleLibraryCollection(lib)
        assert_that([x.title for x in col.library_items], contains('banana', 'bound ok'))

        params['filter'] = 'an'
        col = BundleLibraryCollection(lib)
        assert_that(col.library_items, has_length(0))

    @fudge.patch("nti.app.contentlibrary.workspaces.adapters.get_current_request")
    def testLibraryCollection(self, mock_current_request):
        mock_current_request.is_callable().returns(self.request)
        bundles = []
        for title, createdTime in ( (u'tiger', 20),
                                    (u'banana', 30),
                                    (u'bound ok', 40)):
            bundles.append(PublishableContentPackageBundle(title=title, createdTime=createdTime))

        lib = fudge.Fake('library').has_attr(contentPackages=[])
        col = LibraryCollection(lib)
        assert_that(col.library_items, has_length(0))

        lib = fudge.Fake('library').has_attr(contentPackages=bundles)
        col = LibraryCollection(lib)
        assert_that([x.title for x in col.library_items], contains('banana', 'bound ok', 'tiger'))

        params = self.request.params
        params['sortOn'] = 'title'
        params['sortOrder'] = 'descending'

        col = LibraryCollection(lib)
        assert_that([x.title for x in col.library_items], contains('tiger', 'bound ok', 'banana'))

        params['filter'] = 'b'
        col = LibraryCollection(lib)
        assert_that([x.title for x in col.library_items], contains('bound ok', 'banana'))

        params['searchTerm'] = 't'
        col = LibraryCollection(lib)
        assert_that([x.title for x in col.library_items], contains('tiger'))
