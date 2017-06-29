#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import assert_that

from nti.contentlibrary.bundle import PublishableContentPackageBundle

from nti.externalization.externalization import to_external_object

from nti.app.contentlibrary.tests import PersistentApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS


class TestBundleViews(ApplicationLayerTest):

    layer = PersistentApplicationTestLayer
    default_origin = 'http://platform.ou.edu'

    pkg_ntiid = u'tag:nextthought.com,2011-10:OU-HTML-CS1323_F_2015_Intro_to_Computer_Programming.introduction_to_computer_programming'
    
    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_create_bundle(self):
        href = '/dataserver2/ContentBundles'
        bundle = PublishableContentPackageBundle(title=u'Bleach',
                                                 description=u'Manga bleach')
        ext_obj = to_external_object(bundle)
        ext_obj.pop('NTIID', None)
        ext_obj.pop('ntiid', None)
        ext_obj['ContentPackages'] = [self.pkg_ntiid]
        
        res = self.testapp.post_json(href, ext_obj, status=201)
        assert_that(res.json_body, has_entry('NTIID', is_not(none())))
        assert_that(res.json_body, has_entry('title', is_('Bleach')))
