
import unittest
from apps.channels.tasks import match_channels_to_epg

class TestMatchingOptimization(unittest.TestCase):
    def test_fuzzy_matching_correctness(self):
        # Setup mock data
        channels_data = [
            {
                "id": 1,
                "name": "Test Channel",
                "norm_chan": "test channel",
                "tvg_id": "",
                "epg_data_id": None
            }
        ]

        epg_data = [
            {
                "id": 101,
                "name": "Other Channel",
                "norm_name": "other channel",
                "tvg_id": "other.id",
                "epg_source_priority": 0
            },
            {
                "id": 102,
                "name": "Test Channel",
                "norm_name": "test channel",
                "tvg_id": "test.id",
                "epg_source_priority": 0
            },
            {
                "id": 103,
                "name": "Teest Channel", # Typo, score < 100
                "norm_name": "teest channel",
                "tvg_id": "teest.id",
                "epg_source_priority": 0
            }
        ]

        # Run matching
        result = match_channels_to_epg(channels_data, epg_data, use_ml=False, send_progress=False)

        # Check results
        matched = result["matched_channels"]
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0][2], "test.id") # Should match exact norm_name

    def test_fuzzy_matching_with_bonus(self):
        # Setup mock data where bonus makes a difference
        # Target: "ABC Channel"
        # Candidate 1: "ABC Channel" (score 100) -> but penalized by region?
        # Candidate 2: "ABC Chnl" (score lower) -> but boosted by region?

        # Let's use the logic:
        # region_code = "us"
        # Row 1: "ABC Channel", tvg_id="abc.uk" -> penalty -15
        # Row 2: "ABC Channe", tvg_id="abc.us" -> bonus +15

        channels_data = [
            {
                "id": 1,
                "name": "ABC Channel",
                "norm_chan": "abc channel",
                "tvg_id": "",
                "epg_data_id": None
            }
        ]

        epg_data = [
            {
                "id": 201,
                "name": "ABC Channel", # Exact match 100
                "norm_name": "abc channel",
                "tvg_id": "abc.uk", # Penalty -15 -> 85
                "epg_source_priority": 0
            },
            {
                "id": 202,
                "name": "ABC Channe", # Slightly diff, say 95
                "norm_name": "abc channe",
                "tvg_id": "abc.us", # Bonus +15 -> 110
                "epg_source_priority": 0
            }
        ]

        result = match_channels_to_epg(channels_data, epg_data, region_code="us", use_ml=False, send_progress=False)
        matched = result["matched_channels"]

        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0][2], "abc.us") # Should pick the one with region bonus

    def test_early_exit_logic(self):
        # Ensure that early exit doesn't miss the winner
        # We put the winner at the end of the list with a slightly lower base score but high bonus
        # And a loser at the beginning with high base score but penalty

        channels_data = [
            {
                "id": 1,
                "name": "Winner",
                "norm_chan": "winner",
                "tvg_id": "",
                "epg_data_id": None
            }
        ]

        epg_data = []
        # Add many distractions
        for i in range(100):
            epg_data.append({
                "id": 1000+i,
                "name": f"Distraction {i}",
                "norm_name": f"distraction {i}",
                "tvg_id": f"distraction.{i}",
                "epg_source_priority": 0
            })

        # Add a high base score candidate that gets penalized
        # "Winner" vs "WinnerX" -> score very high (e.g. 90)
        # But penalty -15 -> 75
        epg_data.append({
            "id": 900,
            "name": "WinnerX",
            "norm_name": "winnerx", # High base score
            "tvg_id": "winner.uk", # Penalty
            "epg_source_priority": 0
        })

        # Add the true winner with slightly lower base score but bonus
        # "Winner" vs "Winer" -> score say 80
        # Bonus +15 -> 95
        # So "Winer" (95) should beat "WinnerX" (75)
        # process.extract will return WinnerX first (higher base score)
        # If early exit is wrong, we might stop at WinnerX
        epg_data.append({
            "id": 999,
            "name": "Winer",
            "norm_name": "winer",
            "tvg_id": "winner.us", # Bonus
            "epg_source_priority": 0
        })

        result = match_channels_to_epg(channels_data, epg_data, region_code="us", use_ml=False, send_progress=False)
        matched = result["matched_channels"]

        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0][2], "winner.us")

if __name__ == '__main__':
    unittest.main()
