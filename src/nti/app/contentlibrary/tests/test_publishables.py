#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import none
from hamcrest import is_not
from hamcrest import has_item
from hamcrest import assert_that

from zope import component

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contentlibrary.zodb import RenderableContentPackage

from nti.publishing.interfaces import IPublishables

from nti.app.contentlibrary.tests import PersistentApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver


class TestPublishables(ApplicationLayerTest):

    layer = PersistentApplicationTestLayer
    default_origin = 'http://platform.ou.edu'

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_publishables(self):
        ntiid = u'tag:nextthought.com,2011-10:NTI-HTML-bleach_ichigo'
        package = RenderableContentPackage(title=u'Bleach',
                                           description=u'Manga bleach')
        package.ntiid = ntiid
        package.creator = self.default_username
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            library = component.getUtility(IContentPackageLibrary)
            library.add(package, event=False)
        
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            recordables = component.queryUtility(IPublishables, name="library")
            assert_that(recordables, is_not(none()))
            assert_that(list(recordables.iter_objects()),
                        has_item(package))
