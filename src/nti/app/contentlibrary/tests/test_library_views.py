#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import raises
from hamcrest import calling
from hamcrest import contains
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import has_entries
from hamcrest import assert_that
from hamcrest import has_property

from six.moves import urllib_parse

from zope import component
from zope import interface

from pyramid.router import Router

from pyramid.request import Request

from pyramid.traversal import find_interface

from nti.app.contentlibrary.views.library_views import find_page_info_view_helper

from nti.appserver.httpexceptions import HTTPNotFound

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IContentUnitHrefMapper

from nti.app.contentlibrary.tests import ContentLibraryApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver


@interface.implementer(IContentUnit)
class ContentUnit(object):

    __parent__ = None

    ntiid = None
    lastModified = 0
    href = 'prealgebra'

    def does_sibling_entry_exist(self, unused_sib_name):
        return None

    def __conform__(self, iface):
        if iface == IContentUnitHrefMapper:
            return NIDMapper(self)


@interface.implementer(IContentUnitHrefMapper)
class NIDMapper(object):

    def __init__(self, context):
        href = context.href
        root_package = find_interface(context, IContentPackage)
        if root_package:
            href = root_package.root + '/' + context.href
        href = href.replace('//', '/')
        if not href.startswith('/'):
            href = '/' + href
        self.href = href


class TestApplication(ApplicationLayerTest):

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_library_main(self):
        href = '/dataserver2/users/sjohnson@nextthought.com/Library/Main'

        service_res = self.testapp.get('/dataserver2')
        library_ws, = [
            x for x in service_res.json_body['Items'] if x['Title'] == 'Library'
        ]

        assert_that(library_ws, has_entry('Items', has_length(1)))
        main_col = library_ws['Items'][0]
        assert_that(main_col,
                    has_entry('href',  urllib_parse.unquote(href)))

        res = self.testapp.get(href)
        assert_that(res.cache_control, has_property('max_age', 0))
        assert_that(res.json_body,
                    has_entries('href', href,
                                'titles', is_([])))

    @WithSharedApplicationMockDS
    def test_unicode_in_page_href(self):

        with mock_dataserver.mock_db_trans(self.ds):
            unit = ContentUnit()
            unit.ntiid = u'\u2122'
            request = Request.blank('/')
            request.possible_site_names = ()
            gsm = component.getGlobalSiteManager()
            request.invoke_subrequest = Router(gsm).invoke_subrequest
            request.environ['REMOTE_USER'] = 'foo'
            request.environ['repoze.who.identity'] = {
                'repoze.who.userid': 'foo'
            }
            assert_that(calling(find_page_info_view_helper).with_args(request, unit),
                        raises(HTTPNotFound))


class TestApplicationContent(ApplicationLayerTest):

    layer = ContentLibraryApplicationTestLayer

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_sub_page_info(self):

        href = '/dataserver2/NTIIDs/tag:nextthought.com,2011-10:USSC-HTML-Cohen.22'

        res = self.testapp.get(href,
                               headers={"Accept": 'application/json'})

        href = self.require_link_href_with_rel(res.json_body, 'content')
        assert_that(href,
                    is_('/TestFilesystem/tag_nextthought_com_2011-10_USSC-HTML-Cohen_18.html#22'))

        self.require_link_href_with_rel(res.json_body, 'package')
        assert_that(res.json_body,
                    has_entry('ContentPackageNTIID', 'tag:nextthought.com,2011-10:USSC-HTML-Cohen.cohen_v._california.'))

        assert_that(res.json_body,
                    has_entry('RootURL', '/TestFilesystem/'))


class TestApplicationBundles(ApplicationLayerTest):

    layer = ContentLibraryApplicationTestLayer

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_bundle_library_main(self):
        href = '/dataserver2/users/sjohnson@nextthought.com/ContentBundles/VisibleContentBundles'

        service_res = self.testapp.get('/dataserver2')
        library_ws, = [
            x for x in service_res.json_body['Items'] if x['Title'] == 'ContentBundles'
        ]

        assert_that(library_ws, has_entry('Items', has_length(1)))
        main_col = library_ws['Items'][0]
        assert_that(main_col,
                    has_entry('href', urllib_parse.unquote(href)))

        res = self.testapp.get(href)
        assert_that(res.cache_control, has_property('max_age', 0))
        assert_that(res.json_body,
                    has_entries('href', href,
                                'titles', has_length(2)))

        titles = res.json_body['titles']
        package = next(x for x in titles if x['ntiid'] == u'tag:nextthought.com,2011-10:NTI-Bundle-ABundle')
        assert_that(package,
                    has_entry('ContentPackages',
                              contains(has_entry('Class', 'ContentPackage'))))

        expected = '/dataserver2/%2B%2Betc%2B%2Bbundles/bundles/tag%3Anextthought.com%2C2011-10%3ANTI-Bundle-ABundle/DiscussionBoard'
        expected = urllib_parse.unquote(expected)
        assert_that(urllib_parse.unquote(self.require_link_href_with_rel(package, 'DiscussionBoard')),
                    is_(expected))

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_ipad_hack(self):
        href = '/dataserver2/users/sjohnson@nextthought.com/ContentBundles/VisibleContentBundles'

        res = self.testapp.get(href,
                               extra_environ={'HTTP_USER_AGENT': "NTIFoundation DataLoader NextThought/1.2.0/46149 (x86_64; 7.1)"})

        package = res.json_body['titles'][0]
        assert_that(package,
                    has_entry('ContentPackages',
                              contains('tag:nextthought.com,2011-10:USSC-HTML-Cohen.cohen_v._california.')))
