#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import empty
from hamcrest import is_not
from hamcrest import assert_that
from hamcrest import not_none
from hamcrest import has_entry

from zope.component import eventtesting

from zope.interface.interfaces import IRegistered

from nti.contentlibrary.interfaces import IContentPackageLibraryModifiedOnSyncEvent

from nti.app.contentlibrary.tests import ContentLibraryApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS


class TestSyncViews(ApplicationLayerTest):

    layer = ContentLibraryApplicationTestLayer

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_sync_all_libraries(self):
        href = '/dataserver2/@@SyncAllLibraries'

        eventtesting.clearEvents()
        self.testapp.post(href)

        # We're outside the transaction now, but we can check
        # that we got some events. We would have done ObjectAdded
        # for all the new site libraries for the first time, plus
        # the Will/Modified/DidSync events...
        # XXX: NOTE: We depend on having some of the nti.app.sites
        # packages installed at test time for this to work.

        regs = eventtesting.getEvents(IRegistered)
        assert_that(regs, is_not(empty()))

        event = IContentPackageLibraryModifiedOnSyncEvent
        syncd = eventtesting.getEvents(event)
        assert_that(syncd, is_not(empty()))

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_lock_ops(self):
        self.testapp.post('/dataserver2/@@SetSyncLock', status=204)
        self.testapp.get('/dataserver2/@@IsSyncInProgress', status=200)
        self.testapp.post('/dataserver2/@@RemoveSyncLock', status=204)
        self.testapp.get('/dataserver2/@@LastSyncTime', status=200)
        
    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_metadata_view(self):
        res = self.testapp.get('/dataserver2/users/sjohnson@nextthought.com/SiteAdmin')
        href = self.require_link_href_with_rel(res.json_body, 'SyncMetadata')
        
        res = self.testapp.get(href)

        assert_that(res.json_body, has_entry('lastSynchronized', not_none()))
        assert_that(res.json_body, has_entry('isLocked', not_none()))
