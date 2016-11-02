from charmtest import CharmTest

from fakes import FakeJenkins


class JenkinsTest(CharmTest):

    def setUp(self):
        super().setUp()
        self.fakes.jenkins = self.useFixture(FakeJenkins())
