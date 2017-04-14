#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904


from hamcrest import is_
from hamcrest import all_of
from hamcrest import is_not
from hamcrest import has_item
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import greater_than_or_equal_to
does_not = is_not

import datetime
from urllib import quote as UQ

import anyjson as json

import webob.datetime_utils

from zope import component
from zope import interface

from pyramid import traversal

from nti.contentlibrary import interfaces as lib_interfaces

from nti.dataserver import contenttypes

from nti.ntiids import ntiids

from nti.dataserver.tests import mock_dataserver

from nti.app.testing.application_webtest import ApplicationTestLayer
from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.app.testing.webtest import TestApp

from nti.testing.layers import find_test


class _ApplicationLibraryTestLayer(ApplicationTestLayer):

    @classmethod
    def setUp(cls):
        # Must implement!
        pass

    @classmethod
    def tearDown(cls):
        # Must implement!
        pass

    @classmethod
    def testSetUp(cls, test=None):
        test = test or find_test()
        registry = test.config.registry
        cls.cur_lib = registry.queryUtility(lib_interfaces.IContentPackageLibrary)
        cls.new_lib = test._setup_library()
        registry.registerUtility(cls.new_lib)

    @classmethod
    def testTearDown(cls):
        test = find_test()
        registry = test.config.registry
        registry.unregisterUtility(cls.new_lib, 
                                   lib_interfaces.IContentPackageLibrary)
        if cls.cur_lib is not None and test.config.registry is component.getGlobalSiteManager():
            registry.registerUtility(cls.cur_lib, 
                                     lib_interfaces.IContentPackageLibrary)

        del cls.cur_lib
        del cls.new_lib


class TestApplicationLibraryBase(ApplicationLayerTest):
    layer = _ApplicationLibraryTestLayer

    _check_content_link = True
    _stream_type = 'Stream'

    child_ntiid = ntiids.make_ntiid(provider='ou', 
                                    specific='test2',
                                    nttype='HTML')
    child_ordinal = 0

    def _setup_library(self, content_root='/prealgebra/', lastModified=None):
        test_self = self

        @interface.implementer(lib_interfaces.IContentUnit)
        class NID(object):
            ntiid = test_self.child_ntiid
            href = 'sect_0002.html'
            ordinal = test_self.child_ordinal

            __parent__ = None
            __name__ = 'The name'

            lastModified = 1

            def __init__(self):
                self.siblings = dict()

            def with_parent(self, p):
                self.__parent__ = p
                return self

            def does_sibling_entry_exist(self, sib_name):
                return self.siblings.get(sib_name)

            def __conform__(self, iface):
                if iface == lib_interfaces.IContentUnitHrefMapper:
                    return NIDMapper(self)

        @interface.implementer(lib_interfaces.IContentUnitHrefMapper)
        class NIDMapper(object):

            def __init__(self, context):
                root_package = traversal.find_interface(context, 
                                                        lib_interfaces.IContentPackage)
                href = root_package.root + '/' + context.href
                href = href.replace('//', '/')
                if not href.startswith('/'):
                    href = '/' + href

                self.href = href

        @interface.implementer(lib_interfaces.IContentPackage)
        class LibEnt(object):
            root = content_root
            ntiid = test_self.child_ntiid
            ordinal = test_self.child_ordinal
            __parent__ = None

        if lastModified is not None:
            NID.lastModified = lastModified
            LibEnt.lastModified = lastModified

        @interface.implementer(lib_interfaces.IContentPackageLibrary)
        class Lib(object):
            titles = ()
            contentPackages = ()

            def __getitem__(self, key):
                if key != test_self.child_ntiid:
                    raise KeyError(key)
                return NID().with_parent(LibEnt())

            def pathToNTIID(self, ntiid):
                return [NID().with_parent(LibEnt())] if ntiid == test_self.child_ntiid else None

        return Lib()

    @WithSharedApplicationMockDS
    def test_library_accept_json(self):
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user()
        testapp = TestApp(self.app, extra_environ=self._make_extra_environ())

        for accept_type in ('application/json',
                            'application/vnd.nextthought.pageinfo',
                            'application/vnd.nextthought.pageinfo+json'):

            res = testapp.get('/dataserver2/NTIIDs/' + self.child_ntiid,
                              headers={b"Accept": accept_type})
            assert_that(res.status_int, is_(200))

            assert_that(res.content_type, 
                        is_('application/vnd.nextthought.pageinfo+json'))
            assert_that(res.json_body, 
                        has_entry('MimeType', 'application/vnd.nextthought.pageinfo'))
            if self._check_content_link:
                assert_that(res.json_body,
                            has_entry('Links',
                                      has_item(
                                          all_of(
                                              has_entry('rel', 'content'),
                                              has_entry('href', '/prealgebra/sect_0002.html')))))

            assert_that(res.json_body,
                        has_entry('Links',
                                  has_item(
                                      all_of(
                                          has_entry('rel', self._stream_type),
                                          has_entry('href',
                                                    '/dataserver2/users/sjohnson@nextthought.com/Pages(' + self.child_ntiid + ')/' + self._stream_type)))))


class TestApplicationLibrary(TestApplicationLibraryBase):

    @WithSharedApplicationMockDS
    def test_library_redirect(self):
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user()
        testapp = TestApp(self.app)
        # Unauth gets nothing
        testapp.get('/dataserver2/NTIIDs/' + self.child_ntiid, status=401)

        res = testapp.get('/dataserver2/NTIIDs/' + self.child_ntiid,
                          headers={b'accept': str('text/html')},
                          extra_environ=self._make_extra_environ())
        assert_that(res.status_int, is_(303))
        assert_that(res.headers, has_entry('Location',
                                           'http://localhost/prealgebra/sect_0002.html'))

    @WithSharedApplicationMockDS
    def test_library_redirect_with_fragment(self):
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user()

        testapp = TestApp(self.app)

        fragment = "#fragment"
        ntiid = self.child_ntiid + fragment
        res = testapp.get('/dataserver2/NTIIDs/' + ntiid,
                          headers={'accept': str('text/html')},
                          extra_environ=self._make_extra_environ())
        assert_that(res.status_int, is_(303))
        assert_that(res.headers, 
                    has_entry('Location',
                              'http://localhost/prealgebra/sect_0002.html'))

    @WithSharedApplicationMockDS
    def test_library_accept_link(self):
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user()
        testapp = TestApp(self.app)

        res = testapp.get('/dataserver2/NTIIDs/' + self.child_ntiid,
                          headers={
                              b"Accept": "application/vnd.nextthought.link+json"},
                          extra_environ=self._make_extra_environ())
        assert_that(res.status_int, is_(200))

        assert_that(res.content_type, is_(
            'application/vnd.nextthought.link+json'))
        assert_that(res.json_body, has_entry(
            'href', '/prealgebra/sect_0002.html'))

    @WithSharedApplicationMockDS
    def test_directly_set_page_shared_settings_using_field(self):
        with mock_dataserver.mock_db_trans(self.ds):
            user = self._create_user()
            # First, we must put an object so we have a container
            note = contenttypes.Note()
            note.containerId = self.child_ntiid
            user.addContainedObject(note)

        # Ensure we have modification dates on our _NTIIDEntries
        # so that our trump behaviour works as expected
        self.config.registry.registerUtility(
            self._setup_library(lastModified=1000))
        accept_type = 'application/json'
        testapp = TestApp(self.app)
        # To start with, there is no modification info
        res = testapp.get(str('/dataserver2/Objects/' + self.child_ntiid),
                          headers={b"Accept": accept_type},
                          extra_environ=self._make_extra_environ())
        assert_that(res.last_modified, is_(
            datetime.datetime.fromtimestamp(1000, webob.datetime_utils.UTC)))
        orig_etag = res.etag

        data = json.dumps({"sharedWith": ["a@b"]})
        now = datetime.datetime.now(webob.datetime_utils.UTC)
        now = now.replace(microsecond=0)

        res = testapp.put(str('/dataserver2/Objects/' + self.child_ntiid + '/++fields++sharingPreference'),
                          data,
                          headers={b"Accept": accept_type},
                          extra_environ=self._make_extra_environ())
        assert_that(res.status_int, is_(200))

        assert_that(res.content_type, is_(
            'application/vnd.nextthought.pageinfo+json'))
        assert_that(res.content_location, is_(
            UQ('/dataserver2/Objects/' + self.child_ntiid)))
        assert_that(res.json_body, has_entry(
            'MimeType', 'application/vnd.nextthought.pageinfo'))
        assert_that(res.json_body, has_entry(
            'sharingPreference', has_entry('sharedWith', ['a@b'])))
        assert_that(res.json_body, has_entry(
            'href', '/dataserver2/Objects/' + self.child_ntiid))
        # Now there is modification
        assert_that(res.last_modified, is_(greater_than_or_equal_to(now)))
        last_mod = res.last_modified
        # And it is maintained
        res = testapp.get(str('/dataserver2/NTIIDs/' + self.child_ntiid),
                          headers={b"Accept": accept_type},
                          extra_environ=self._make_extra_environ())
        assert_that(res.last_modified, is_(last_mod))

        # We can make a conditional request, and it doesn't match
        res = testapp.get('/dataserver2/NTIIDs/' + self.child_ntiid,
                          headers={b'Accept': accept_type,
                                   b'If-None-Match': orig_etag},
                          extra_environ=self._make_extra_environ(),
                          status=200)
        assert_that(res.etag, is_not(orig_etag))


class TestApplicationLibraryNoSlash(TestApplicationLibrary):

    def _setup_library(self, *args, **kwargs):
        return super(TestApplicationLibraryNoSlash, self)._setup_library(content_root="prealgebra", **kwargs)


class TestRootPageEntryLibrary(TestApplicationLibraryBase):
    child_ntiid = ntiids.ROOT
    _check_content_link = False
    _stream_type = 'RecursiveStream'

    @WithSharedApplicationMockDS
    def test_set_root_page_prefs_inherits(self):
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user()

        testapp = TestApp(self.app)

        # First, put to the root
        now = datetime.datetime.now(webob.datetime_utils.UTC)
        now = now.replace(microsecond=0)

        accept_type = 'application/json'
        data = json.dumps({"sharedWith": ["a@b"]})
        res = testapp.put(str('/dataserver2/NTIIDs/' + ntiids.ROOT + '/++fields++sharingPreference'),
                          data,
                          headers={b"Accept": accept_type},
                          extra_environ=self._make_extra_environ())
        assert_that(res.status_int, is_(200))

        assert_that(res.content_type,
                    is_('application/vnd.nextthought.pageinfo+json'))
        assert_that(res.json_body, 
                    has_entry('MimeType', 'application/vnd.nextthought.pageinfo'))
        assert_that(res.json_body,
                    has_entry('sharingPreference', has_entry('sharedWith', ['a@b'])))
        assert_that(res.json_body, 
                    has_entry('href', '/dataserver2/Objects/' + ntiids.ROOT))

        # Then, reset the library so we have a child, and get the child
        self.child_ntiid = TestApplicationLibrary.child_ntiid
        self.config.registry.registerUtility(self._setup_library())

        testapp = TestApp(self.app)
        res = testapp.get('/dataserver2/NTIIDs/' + self.child_ntiid,
                          headers={"Accept": accept_type},
                          extra_environ=self._make_extra_environ())
        assert_that(res.status_int, is_(200))
        assert_that(res.json_body, 
                    has_entry('MimeType', 'application/vnd.nextthought.pageinfo'))
        assert_that(res.json_body, 
                    has_entry('sharingPreference', has_entry('sharedWith', ['a@b'])))
        # Now there is modification
        assert_that(res.last_modified, is_(greater_than_or_equal_to(now)))
