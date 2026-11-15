from django.test import SimpleTestCase
from django.urls import reverse


class StoryApiTests(SimpleTestCase):
    def test_rome_story_has_ordered_sourced_events_in_review(self):
        response = self.client.get(reverse("story-detail", args=["expansion-de-roma"]))
        self.assertEqual(response.status_code, 200)
        story = response.json()
        self.assertEqual(story["slug"], "expansion-de-roma")
        self.assertEqual([item["order"] for item in story["events"]], list(range(1, 6)))
        for item in story["events"]:
            self.assertEqual(item["evidence_status"], "under_review")
            self.assertTrue(item["sources"][0]["locator"])
            self.assertIsNone(item["place"]["coordinates"])
            self.assertNotEqual(item["date"]["start_year"], 0)
            self.assertLessEqual(item["date"]["start_year"], item["date"]["end_year"])

    def test_unknown_story_returns_json_404(self):
        response = self.client.get(reverse("story-detail", args=["desconocida"]))
        self.assertEqual(response.status_code, 404)
        self.assertIn("detail", response.json())

    def test_endpoint_is_read_only(self):
        self.assertEqual(self.client.post(reverse("story-detail", args=["expansion-de-roma"])).status_code, 405)
