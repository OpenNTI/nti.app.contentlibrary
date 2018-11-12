#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

from hamcrest import has_entries
from hamcrest import assert_that

from zope import component

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.contentlibrary.contentunit import ContentUnit

from nti.contenttypes.completion.interfaces import ICompletableItemCompletionPolicy

from nti.externalization.externalization import to_external_object


class TestCompletion(ApplicationLayerTest):

    def test_externalization(self):
        obj = ContentUnit()
        policy = ICompletableItemCompletionPolicy(obj)
        assert_that(to_external_object(policy), has_entries({'Class': 'DefaultContentUnitCompletionPolicy',
                                                             'offers_completion_certificate': False}))
