from django.test import TestCase, override_settings
from apps.channels.models import Channel, Logo, ChannelGroup
from apps.epg.models import EPGData, EPGSource
from apps.channels.tasks import set_channels_logos_from_epg
from unittest.mock import patch, MagicMock

@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class LogoOptimizationTest(TestCase):
    def setUp(self):
        # Patch RedisClient globally for the test
        self.redis_patcher = patch('core.utils.RedisClient.get_client')
        self.mock_redis_cls = self.redis_patcher.start()
        self.mock_redis = MagicMock()
        self.mock_redis.get.return_value = None
        self.mock_redis.set.return_value = True
        self.mock_redis_cls.return_value = self.mock_redis

        # Patch websocket update
        self.ws_patcher = patch('core.utils.send_websocket_update')
        self.ws_patcher.start()

        self.source = EPGSource.objects.create(name="Test Source", source_type="dummy")
        self.group = ChannelGroup.objects.create(name="Test Group")

    def tearDown(self):
        self.redis_patcher.stop()
        self.ws_patcher.stop()

    def test_logo_creation_and_assignment(self):
        # Create 10 channels with same icon URL
        url = "http://example.com/logo.png"
        channels = []
        for i in range(10):
            epg = EPGData.objects.create(
                name=f"Channel {i}",
                tvg_id=f"ch_{i}",
                icon_url=url,
                epg_source=self.source
            )
            ch = Channel.objects.create(
                name=f"Channel {i}",
                channel_number=i+1,
                epg_data=epg,
                channel_group=self.group
            )
            channels.append(ch)

        # Run task
        set_channels_logos_from_epg([c.id for c in channels])

        # Verify only 1 logo created
        self.assertEqual(Logo.objects.count(), 1)
        logo = Logo.objects.first()
        self.assertEqual(logo.url, url)

        # Verify all channels have this logo
        for ch in Channel.objects.all():
            self.assertEqual(ch.logo, logo)

    def test_logo_reuse(self):
        # Create existing logo
        url = "http://example.com/existing.png"
        existing_logo = Logo.objects.create(name="Existing", url=url)

        # Create channel using it
        epg = EPGData.objects.create(name="Ch1", tvg_id="ch1", icon_url=url, epg_source=self.source)
        ch = Channel.objects.create(name="Ch1", channel_number=1, epg_data=epg, channel_group=self.group)

        # Run task
        set_channels_logos_from_epg([ch.id])

        self.assertEqual(Logo.objects.count(), 1)
        ch.refresh_from_db()
        self.assertEqual(ch.logo, existing_logo)
