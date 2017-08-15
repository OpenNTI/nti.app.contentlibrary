#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_in
from hamcrest import is_not
from hamcrest import has_key
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_entries
does_not = is_not

from nti.app.contentlibrary.exporter.mixins import AssetExporterMixin

from nti.contenttypes.presentation.interfaces import INTIVideo

from nti.ntiids.ntiids import hash_ntiid
from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.contentlibrary.tests import PersistentApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver


class TestMixins(ApplicationLayerTest):

    layer = PersistentApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    package = u"tag:nextthought.com,2011-10:OU-HTML-CS1323_F_2015_Intro_to_Computer_Programming.introduction_to_computer_programming"

    video = u'tag:nextthought.com,2011-10:OU-NTIVideo-CS1323_F_2015_Intro_to_Computer_Programming.ntivideo.video_janux_videos'

    container = u'tag:nextthought.com,2011-10:OU-HTML-CS1323_F_2015_Intro_to_Computer_Programming.lec:01.04_LESSON'

    salt = '100'

    @WithSharedApplicationMockDS(testapp=False, users=False)
    def test_export(self):

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            package = find_object_with_ntiid(self.package)
            exporter = AssetExporterMixin()
            result = exporter.do_export(package, INTIVideo, False, self.salt)
            assert_that(result, 
                        has_entries('Containers', has_length(32),
                                    'Items', has_length(92)))
            
            salted_video = hash_ntiid(self.video, self.salt)
            assert_that(result,
                        has_entry('Items', has_entry(salted_video, has_entry('NTIID', salted_video))))
            
            salted_container = hash_ntiid(self.container, self.salt)
            assert_that(result,
                        has_entry('Containers', has_key(salted_container)))
            
            items = result['Containers'][salted_container]
            assert_that(salted_video, is_in(items))
