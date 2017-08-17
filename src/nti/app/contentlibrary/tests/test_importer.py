#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_not
from hamcrest import has_length
from hamcrest import assert_that
does_not = is_not

import os

from nti.app.contentlibrary.importer import AssetImporterMixin

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.contentlibrary.tests import PersistentApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver


class TestImporter(ApplicationLayerTest):
 
    layer = PersistentApplicationTestLayer
 
    default_origin = 'http://janux.ou.edu'
 
    package = u"tag:nextthought.com,2011-10:OU-HTML-CS1323_F_2015_Intro_to_Computer_Programming.introduction_to_computer_programming"
 
 
    @WithSharedApplicationMockDS(testapp=False, users=False)
    def test_export(self):
 
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            package = find_object_with_ntiid(self.package)
            importer = AssetImporterMixin()
            source = os.path.join(os.path.dirname(__file__), 'video_index.json')
            with open(source, "r") as fp:
                added, removed = importer.do_import(package, fp, 'video_index.json')
            assert_that(added, has_length(94))
            assert_that(removed, has_length(92))
