#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import assert_that
from hamcrest import contains_string

import os.path

import urllib

from zope import component

from nti.dictserver.storage import TrivialExcelCSVDataStorage

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.appserver.tests.test_application import TestApp

from nti.dataserver.tests import mock_dataserver

from nti.dictserver.tests import test_dictionary


class TestApplicationGlossary(ApplicationLayerTest):

    @WithSharedApplicationMockDS
    def test_path_with_parens_no_container_no_verify(self):
        # "We can hit the glossary of a new container. Does no real verification."
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user()

        csv_dict = TrivialExcelCSVDataStorage(os.path.join(os.path.dirname(test_dictionary.__file__),
                                                           'nti_content_glossary.csv'))
        component.provideUtility(csv_dict)

        try:
            testapp = TestApp(self.app)
            path = '/dataserver2/users/sjohnson@nextthought.com/Pages(tag:NewcontainerResource)/Glossary/demo'
            # path = urllib.quote( path )
            res = testapp.get(path, extra_environ=self._make_extra_environ())

            assert_that(res.body, contains_string(str('xml-stylesheet')))

            path = '/dataserver2/users/sjohnson@nextthought.com/Pages(tag:NewcontainerResource)/Glossary/institutional theory'
            path = urllib.quote(path)
            res = testapp.get(path, extra_environ=self._make_extra_environ())

            assert_that(res.body, contains_string(str('xml-stylesheet')))
            assert_that(res.body, contains_string(str('institutional')))
        finally:
            component.getGlobalSiteManager().unregisterUtility(csv_dict)
