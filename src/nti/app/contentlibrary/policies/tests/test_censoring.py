#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from zope import component

from nti.app.contentlibrary.policies import censoring

from nti.contentfragments.censor import DefaultCensoredContentPolicy

from nti.dataserver import interfaces as nti_interfaces

from nti.appserver.policies.tests.test_application_censoring import CensorTestMixin

from nti.app.contentlibrary.tests import ExLibraryApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS


class TestApplicationCensoringWithDefaultPolicyForAllUsers(CensorTestMixin, ApplicationLayerTest):

    layer = ExLibraryApplicationTestLayer

    def setUp(self):
        super(TestApplicationCensoringWithDefaultPolicyForAllUsers, self).setUp()
        component.provideAdapter(DefaultCensoredContentPolicy,
                                 adapts=(nti_interfaces.IUser, None))
        component.provideAdapter(censoring.user_filesystem_censor_policy)

    def tearDown(self):
        gsm = component.getGlobalSiteManager()
        gsm.unregisterAdapter(DefaultCensoredContentPolicy,
                              required=(nti_interfaces.IUser, None))
        gsm.unregisterAdapter(censoring.user_filesystem_censor_policy)

    @WithSharedApplicationMockDS
    def test_censoring_can_be_disabled_by_file_in_library(self):
        self._do_test_censor_note("tag:nextthought.com,2011-10:MN-HTML-Uncensored.cosmetology",
                                  censored=False)

    @WithSharedApplicationMockDS
    def test_censoring_cannot_be_disabled_for_kids(self):
        # "The ICoppaUser flag trumps the no-censoring flag"
        self._do_test_censor_note("tag:nextthought.com,2011-10:MN-HTML-Uncensored.cosmetology",
                                  censored=True,
                                  extra_ifaces=(nti_interfaces.ICoppaUser,))

    @WithSharedApplicationMockDS
    def test_censor_note_not_in_library_enabled_for_kids(self):
        # "If we post a note to a container we don't recognize, we  get censored if we are a kid"
        self._do_test_censor_note('tag:not_in_library',
                                  censored=True,
                                  extra_ifaces=(nti_interfaces.ICoppaUser,))
