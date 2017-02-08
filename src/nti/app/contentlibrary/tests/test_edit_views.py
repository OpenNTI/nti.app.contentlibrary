#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_property

from zope import component

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contentlibrary.zodb import RenderableContentPackage

from nti.externalization.externalization import to_external_object

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.recorder.interfaces import ITransactionRecordHistory

from nti.app.contentlibrary.tests import PersistentApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver


class TestEditViews(ApplicationLayerTest):

    layer = PersistentApplicationTestLayer
    default_origin = b'http://platform.ou.edu'

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_create_package(self):
        href = '/dataserver2/Library'
        package = RenderableContentPackage(title='Bleach',
                                           description='Manga bleach')
        ext_obj = to_external_object(package)
        ext_obj.pop('NTIID', None)
        ext_obj.pop('ntiid', None)

        res = self.testapp.post_json(href, ext_obj, status=201)
        assert_that(res.json_body, has_entry('NTIID', is_not(none())))
        assert_that(res.json_body, has_entry('title', is_('Bleach')))

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_update_package(self):
        ntiid = u'tag:nextthought.com,2011-10:NTI-HTML-bleach_ichigo'
        package = RenderableContentPackage(title='Bleach',
                                           description='Manga bleach')
        package.ntiid = ntiid
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            library = component.getUtility(IContentPackageLibrary)
            library.add(package, event=False)
            ext_obj = to_external_object(package)
        ext_obj['description'] = 'Ichigo and Rukia'

        href = '/dataserver2/Library/%s' % ntiid
        res = self.testapp.put_json(href, ext_obj, status=200)
        assert_that(res.json_body, has_entry('NTIID', is_(ntiid)))
        assert_that(res.json_body,
                    has_entry('description', is_('Ichigo and Rukia')))

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_contents(self):
        ntiid = u'tag:nextthought.com,2011-10:NTI-HTML-bleach_ichigo'
        package = RenderableContentPackage(title='Bleach',
                                           description='Manga bleach')
        package.ntiid = ntiid
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            library = component.getUtility(IContentPackageLibrary)
            library.add(package, event=False)

        href = '/dataserver2/Library/%s/@@contents' % ntiid
        res = self.testapp.get(href, status=200)
        assert_that(res.body, has_length(0))

        self.testapp.put(href,
                         upload_files=[
                             ('contents', 'contents.rst', b'ichigo')],
                         status=200)
        res = self.testapp.get(href, status=200)
        assert_that(res.body, has_length(6))

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            package = find_object_with_ntiid(ntiid)
            assert_that(package, 
                        has_property('contents', is_(b'ichigo')))
            assert_that(package,
                        has_property('contentType', is_(b'text/x-rst')))
            history = ITransactionRecordHistory(package)
            assert_that(history.records(), has_length(1))
