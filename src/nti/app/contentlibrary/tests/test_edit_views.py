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
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_property

from nti.testing.matchers import is_empty

import fudge

from zope import component

from zope.intid.interfaces import IIntIds

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contentlibrary.utils import export_content_package

from nti.contentlibrary.zodb import RenderableContentPackage

from nti.externalization.externalization import to_external_object

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.recorder.interfaces import ITransactionRecordHistory

from nti.recorder.index import get_transactions

from nti.app.contentlibrary.tests import PersistentApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver


class TestEditViews(ApplicationLayerTest):

    layer = PersistentApplicationTestLayer
    default_origin = 'http://platform.ou.edu'

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_create_package(self):
        href = '/dataserver2/Library'
        package = RenderableContentPackage(title=u'Bleach',
                                           description=u'Manga bleach')
        ext_obj = to_external_object(package)
        ext_obj.pop('NTIID', None)
        ext_obj.pop('ntiid', None)

        res = self.testapp.post_json(href, ext_obj, status=201)
        assert_that(res.json_body, has_entry('NTIID', is_not(none())))
        assert_that(res.json_body, has_entry('title', is_('Bleach')))

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_update_package(self):
        ntiid = u'tag:nextthought.com,2011-10:NTI-HTML-bleach_ichigo'
        package = RenderableContentPackage(title=u'Bleach',
                                           description=u'Manga bleach')
        package.ntiid = ntiid
        package.creator = self.default_username
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

        ext_obj = {'icon': 'http://bleach.org/ichigo.png'}
        res = self.testapp.put_json(href, ext_obj, status=200)
        assert_that(res.json_body,
                    has_entry('icon', is_('http://bleach.org/ichigo.png')))

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_contents(self):
        ntiid = u'tag:nextthought.com,2011-10:NTI-HTML-bleach_ichigo'
        package = RenderableContentPackage(title=u'Bleach',
                                           description=u'Manga bleach')
        package.ntiid = ntiid
        package.creator = self.default_username
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            library = component.getUtility(IContentPackageLibrary)
            library.add(package, event=False)

        href = '/dataserver2/Library/%s' % ntiid
        res = self.testapp.get(href, status=200)
        self.require_link_href_with_rel(res.json_body, 'contents')
        
        href = '/dataserver2/Library/%s/@@contents?attachment=True' % ntiid
        res = self.testapp.get(href, status=200)
        assert_that(res.body, has_length(0))

        self.testapp.put(href,
                         upload_files=[
                             ('contents', 'contents.rst', b'ichigo')],
                         status=200)
        res = self.testapp.get(href, status=200)
        assert_that(res.body, has_length(6))

        with mock_dataserver.mock_db_trans(self.ds, site_name=u'platform.ou.edu'):
            package = find_object_with_ntiid(ntiid)
            assert_that(package,
                        has_property('contents', is_(b'ichigo')))
            assert_that(package,
                        has_property('contentType', is_(b'text/x-rst')))
            history = ITransactionRecordHistory(package)
            assert_that(history.records(), has_length(1))

        href = '/dataserver2/Library/%s/@@contents' % ntiid
        res = self.testapp.get(href, status=200)
        assert_that(res.json_body,
                    has_entry('contentType', is_(str('text/x-rst'))))
        assert_that(res.json_body,
                    has_entry('data', is_(str('ichigo'))))

        with mock_dataserver.mock_db_trans(self.ds, site_name=u'platform.ou.edu'):
            package = find_object_with_ntiid(ntiid)
            res = export_content_package(package, True)
            assert_that(res,
                        has_entry('contentType', is_(str('text/x-rst'))))
            assert_that(res,
                        has_entry('contents', is_(u'eJzLTM7ITM8HAAiDAnQ=')))


    @WithSharedApplicationMockDS(users=True, testapp=True)
    @fudge.patch('nti.app.contentlibrary.views.edit_views.resolve_content_unit_associations')
    def test_delete(self, mock_rca):
        mock_rca.is_callable().with_args().returns(('foo',))
        ntiid = u'tag:nextthought.com,2011-10:NTI-HTML-bleach_ichigo'
        package = RenderableContentPackage(title=u'Bleach',
                                           description=u'Manga bleach')
        package.ntiid = ntiid
        package.creator = self.default_username
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            library = component.getUtility(IContentPackageLibrary)
            library.add(package, event=False)
            
        ext_obj = {'description' : 'Ichigo and Rukia'}
        href = '/dataserver2/Library/%s' % ntiid
        self.testapp.put_json(href, ext_obj, status=200)
        with mock_dataserver.mock_db_trans(self.ds, site_name=u'platform.ou.edu'):
            intids = component.getUtility(IIntIds)
            package = find_object_with_ntiid(ntiid)
            history = ITransactionRecordHistory(package)
            pkg_trxs = {intids.queryId(x) for x in history.records()}
            pkg_trxs.discard(None)
            
        href = '/dataserver2/Library/%s' % ntiid
        self.testapp.delete(href, status=409)

        href = '/dataserver2/Library/%s?force=true' % ntiid
        self.testapp.delete(href, status=204)

        href = '/dataserver2/Library/%s' % ntiid
        self.testapp.get(href, status=404)
        
        with mock_dataserver.mock_db_trans(self.ds, site_name=u'platform.ou.edu'):
            all_trxs = {intids.queryId(x) for x in get_transactions()}
            all_trxs.discard(None)
        
        assert_that(all_trxs.intersection(pkg_trxs),
                    is_empty())
