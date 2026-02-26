
import time
import tracemalloc
import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock django settings
import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        INSTALLED_APPS=[
            'apps.channels',
            'apps.epg',
            'apps.accounts',
            'apps.m3u',
            'core',
            'django_celery_beat',
            'django.contrib.auth',
            'django.contrib.contenttypes',
        ],
        DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
    )
    django.setup()

from apps.channels.tasks import match_channels_to_epg

# Mock ML components to avoid heavy loading time
class MockSentenceTransformer:
    def encode(self, texts, convert_to_tensor=True):
        import torch
        # Return fake tensors of correct shape
        if isinstance(texts, str):
            return torch.rand(384)
        return torch.rand(len(texts), 384)

class MockUtil:
    def cos_sim(self, a, b):
        import torch
        # Return fake similarity scores
        return torch.rand(1, b.shape[0])

# Monkey patch get_sentence_transformer
import apps.channels.tasks
apps.channels.tasks.get_sentence_transformer = lambda: (MockSentenceTransformer(), MockUtil())

def benchmark_ml_matching():
    print("Benchmarking ML matching loop...")

    # 500 channels that will FAIL fuzzy match and trigger ML
    channels_data = [
        {"id": i, "name": f"Channel {i}", "tvg_id": "", "norm_chan": f"channel {i}"}
        for i in range(500)
    ]

    # 2000 EPG entries
    epg_data = [
        {"id": j, "name": f"EPG {j}", "tvg_id": f"epg{j}", "norm_name": f"epg {j}", "epg_source_priority": 1}
        for j in range(2000)
    ]

    # Some EPGs without norm_name to test filtering logic
    for k in range(100):
        epg_data[k]["norm_name"] = ""

    tracemalloc.start()
    start_time = time.time()

    # Force ML path by ensuring fuzzy match fails (threshold is 40)
    # Our names are "Channel X" vs "EPG Y", fuzzy ratio will be low
    match_channels_to_epg(channels_data, epg_data, region_code=None, use_ml=True, send_progress=False)

    end_time = time.time()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"Time: {end_time - start_time:.4f} seconds")
    print(f"Memory peak: {peak / 1024:.2f} KB")

if __name__ == "__main__":
    benchmark_ml_matching()
