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
from hamcrest import has_property

import os
import shutil
import tempfile

import fudge

from nti.cabinet.mixins import SourceFile

from nti.contentlibrary.bundle import PublishableContentPackageBundle

from nti.externalization.externalization import to_external_object

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.contentlibrary.tests import PersistentApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver


class TestBundleViews(ApplicationLayerTest):

    layer = PersistentApplicationTestLayer
    default_origin = 'http://platform.ou.edu'

    pkg_ntiid = u'tag:nextthought.com,2011-10:OU-HTML-CS1323_F_2015_Intro_to_Computer_Programming.introduction_to_computer_programming'
    
    def presentation_assets_zip(self, tmpdir=None):
        tmpdir = tmpdir or tempfile.mkdtemp()
        outfile = os.path.join(tmpdir, "assets")
        path = os.path.join(os.path.dirname(__file__),
                            "presentation-assets") 
        return shutil.make_archive(outfile, "zip", path)

    @WithSharedApplicationMockDS(users=True, testapp=True)
    @fudge.patch('nti.app.contentlibrary.views.bundle_views.get_all_sources')
    def test_create_bundle(self, mock_src):
        tmpdir = tempfile.mkdtemp()
        try:
            path = self.presentation_assets_zip(tmpdir)
            with open(path, "rb") as fp:
                source = SourceFile("assets.zip", fp.read())
            mock_src.is_callable().with_args().returns({"assets.zip":source})
            href = '/dataserver2/ContentBundles'
            bundle = PublishableContentPackageBundle(title=u'Bleach',
                                                     description=u'Manga bleach')
            ext_obj = to_external_object(bundle)
            ext_obj.pop('NTIID', None)
            ext_obj.pop('ntiid', None)
            ext_obj['ContentPackages'] = [self.pkg_ntiid]
            
            res = self.testapp.post_json(href, ext_obj, status=201)
            assert_that(res.json_body, has_entry('OID', is_not(none())))
            assert_that(res.json_body, has_entry('NTIID', is_not(none())))
            assert_that(res.json_body, has_entry('title', is_('Bleach')))
            ntiid = res.json_body['OID']

            with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
                bundle = find_object_with_ntiid(ntiid)
                assert_that(bundle, 
                            has_property('_presentation_assets', is_not(none())))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
