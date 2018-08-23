#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

from hamcrest import none
from hamcrest import is_not
from hamcrest import has_item
from hamcrest import assert_that

from zope import component

from nti.app.contentlibrary.tests import PersistentApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contentlibrary.zodb import RenderableContentPackage

from nti.contenttypes.completion.interfaces import ICompletables

from nti.dataserver.tests import mock_dataserver


class TestCompletables(ApplicationLayerTest):

    layer = PersistentApplicationTestLayer
    default_origin = 'http://platform.ou.edu'

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_completables(self):
        ntiid = u'tag:nextthought.com,2011-10:NTI-HTML-bleach_ichigo'
        package = RenderableContentPackage(title=u'Bleach',
                                           description=u'Manga bleach')
        package.ntiid = ntiid
        package.creator = self.default_username
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            library = component.getUtility(IContentPackageLibrary)
            library.add(package, event=False)
        
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            completables = component.queryUtility(ICompletables, name="library")
            assert_that(completables, is_not(none()))
            assert_that(list(completables.iter_objects()),
                        has_item(package))
