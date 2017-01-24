import os

from systemfixtures.matchers import HasOwnership
from charmtest import CharmTest

from charms.layer.jenkins import paths
from charms.layer.jenkins.storage import Storage
from states import State


class StorageTest(CharmTest):

    def setUp(self):
        super(StorageTest, self).setUp()
        self.useFixture(State(self.fakes))
        self.fakes.fs.add(os.path.dirname(paths.HOME))
        os.makedirs(paths.HOME)
        os.chown(paths.HOME, 123, 123)
        self.storage_dir = paths.HOME + '-storage'
        os.makedirs(self.storage_dir)

    def test_link(self):
        Storage().link_home(self.storage_dir)
        self.assertTrue(os.path.islink(paths.HOME))
        self.assertEqual(os.path.realpath(paths.HOME), self.storage_dir)
        self.assertThat(paths.HOME, HasOwnership(123, 123))

        # Second run paths.HOME is a link
        Storage().link_home(self.storage_dir)
        self.assertTrue(os.path.islink(paths.HOME))
        self.assertEqual(os.path.realpath(paths.HOME), self.storage_dir)
        self.assertThat(paths.HOME, HasOwnership(123, 123))

    def test_link_existing_backup(self):
        with open(os.path.join(self.storage_dir, "touched"), 'w') as f:
            f.write("touched")
        os.mkdir(Storage()._backup_dir)
        self.assertRaises(RuntimeError,
                          lambda: Storage().link_home(self.storage_dir))

    def test_unlink(self):
        with open(os.path.join(self.storage_dir, "touched"), 'w') as f:
            f.write("touched")
        Storage().link_home(self.storage_dir)

        Storage().unlink_home()
        self.assertFalse(os.path.islink(paths.HOME))
        self.assertThat(paths.HOME, HasOwnership(123, 123))

        # Second run is a no-op
        Storage().unlink_home()
        self.assertFalse(os.path.islink(paths.HOME))
        self.assertThat(paths.HOME, HasOwnership(123, 123))

    def test_unlink_no_backup(self):
        Storage().link_home(self.storage_dir)

        Storage().unlink_home()
        self.assertFalse(os.path.islink(paths.HOME))
        self.assertThat(paths.HOME, HasOwnership(123, 123))
