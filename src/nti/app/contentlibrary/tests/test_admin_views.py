#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import greater_than_or_equal_to
does_not = is_not

from nti.app.contentlibrary.tests import PersistentApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS


class TestAdminViews(ApplicationLayerTest):

    layer = PersistentApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_rebuild_library_catalog(self):
        res = self.testapp.post('/dataserver2/Library/@@RebuildContentLibraryCatalog',
                                status=200)
        assert_that(res.json_body,
                    has_entries('Total', is_(greater_than_or_equal_to(0)),
                                'ItemCount', is_(greater_than_or_equal_to(0))))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_rebuild_bundle_catalog(self):
        res = self.testapp.post('/dataserver2/Library/@@RebuildContentBundleCatalog',
                                status=200)
        assert_that(res.json_body,
                    has_entries('Total', is_(greater_than_or_equal_to(0)),
                                'ItemCount', is_(greater_than_or_equal_to(0))))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_all_content_packages(self):
        res = self.testapp.get('/dataserver2/Library/@@AllContentPackages',
                               status=200)
        assert_that(res.json_body,
                    has_entries('TotalItemCount', is_(greater_than_or_equal_to(0)),
                                'ItemCount', is_(greater_than_or_equal_to(0))))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_all_content_package_bundles(self):
        res = self.testapp.get('/dataserver2/Library/@@AllContentPackageBundles',
                               status=200)
        assert_that(res.json_body,
                    has_entries('TotalItemCount', is_(greater_than_or_equal_to(0)),
                                'ItemCount', is_(greater_than_or_equal_to(0))))
