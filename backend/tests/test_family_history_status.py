import unittest
from types import SimpleNamespace
from app.services.family_history_status import family_history_status
from app.models import FamilyHistoryStatus


class FamilyHistoryStatusTests(unittest.TestCase):
    def test_empty_lists_are_not_automatically_denials(self):
        for declaration, expected in ((None, 'not_collected'), ('none', 'no_known_conditions'), ('unknown', 'unknown')):
            profile = SimpleNamespace(onboarding_state={'chat_v1': {'declarations': {'family_history': declaration}}})
            self.assertEqual(family_history_status(profile, []), expected)
            self.assertEqual(family_history_status(profile, [object()]), FamilyHistoryStatus.KNOWN_CONDITIONS)
