#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import none
from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import assert_that

from nti.contentlibrary.zodb import RenderableContentPackage

from nti.externalization.externalization import to_external_object

from nti.app.contentlibrary.tests import ContentLibraryApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS


class TestEditViews(ApplicationLayerTest):

    layer = ContentLibraryApplicationTestLayer

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_create_package(self):
        href = '/dataserver2/Library'
        package = RenderableContentPackage(title='Bleach',
                                           decription='Manga bleach')
        ext_obj = to_external_object(package)
        ext_obj.pop('NTIID', None)
        ext_obj.pop('ntiid', None)

        #res = self.testapp.post_json(href, ext_obj, status=201)
        #assert_that(res.json_body, has_entry('NTIID', is_not(none())))
