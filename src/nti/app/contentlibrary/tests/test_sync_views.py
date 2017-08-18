#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import empty
from hamcrest import is_not
from hamcrest import assert_that
from hamcrest import not_none
from hamcrest import has_entry
from hamcrest import equal_to
from hamcrest import has_key

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
        self.testapp.post('/dataserver2/@@SetSyncLock', status=204)
        
        res = self.testapp.get(href)
        assert_that(res.json_body, has_entry('is_locked', True))
        assert_that(res.json_body, has_entry('holding_user', 'sjohnson@nextthought.com'))
        assert_that(res.json_body, has_entry('last_locked', not_none()))
        assert_that(res.json_body, is_not(has_key('last_released')))
        assert_that(res.json_body, has_entry('last_synchronized', not_none()))
        
        
        res = self.testapp.get('/dataserver2/@@IsSyncInProgress', status=200)
        assert_that(res.json_body, equal_to(True))

        self.testapp.post('/dataserver2/@@RemoveSyncLock', status=204)
        res = self.testapp.get(href)
        
        res = self.testapp.get('/dataserver2/@@IsSyncInProgress', status=200)
        assert_that(res.json_body, equal_to(False))
        
        res = self.testapp.get(href)
        assert_that(res.json_body, has_entry('is_locked', False))
        assert_that(res.json_body, has_entry('holding_user', None))
        assert_that(res.json_body, has_entry('last_released', not_none()))
        assert_that(res.json_body, is_not(has_key('last_locked')))
        assert_that(res.json_body, has_entry('last_synchronized', not_none()))
        
        
class TestSyncableViews(ApplicationLayerTest):
    
    layer = PersistentInstructedCourseApplicationTestLayer
    
    default_origin = b'http://platform.ou.edu'
    
    package_hrefs = ['/dataserver2/NTIIDs/tag%3Anextthought.com%2C2011-10%3AOU-HTML-CS1323_F_2015_Intro_to_Computer_Programming.introduction_to_computer_programming/',
                     '/dataserver2/NTIIDs/tag%3Anextthought.com%2C2011-10%3AOU-HTML-CLC3403_LawAndJustice.clc_3403_law_and_justice/']
    
    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_get_syncable(self):
        for href in self.package_hrefs:
            self.testapp.post(href+"@@Sync")
        
        view_link = '/dataserver2/@@SyncableContentPackages'
        res = self.testapp.get(view_link)
         
        for i in range(len(self.package_hrefs)):
            self.require_link_href_with_rel(res.json_body.get("Items")[i], 'Sync')
        
