import json
from pathlib import Path
import tempfile
import unittest
from skillsbench_replay.maven_support import proxy_settings, replay_mount_and_setup


class MavenSupportTest(unittest.TestCase):
    def test_proxy_reaches_host_from_container(self):
        settings = proxy_settings('http://127.0.0.1:7890')
        self.assertIn('<host>host.docker.internal</host>', settings)
        self.assertIn('<port>7890</port>', settings)
        with self.assertRaises(ValueError):
            proxy_settings('http://user:secret@localhost:7890')

    def test_only_validated_repository_is_mounted_read_only(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / 'repository').mkdir()
            (root / 'ready.json').write_text(json.dumps({'offline_probe_passed': False}))
            with self.assertRaises(ValueError):
                replay_mount_and_setup(root)
            (root / 'ready.json').write_text(json.dumps({'offline_probe_passed': True,
                'default_settings_network_disabled_probe_passed': True}))
            mount, setup = replay_mount_and_setup(root)
            self.assertEqual(mount, ['-v', f'{root.resolve() / "repository"}:/causalflow-maven-repository:ro'])
            self.assertIn('/home/agent/.m2/repository', setup)
            self.assertNotIn('settings.xml', setup)
            self.assertNotIn('/app/workspace', setup)


if __name__ == '__main__':
    unittest.main()
