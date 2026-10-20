import unittest

from chatbot.nlp_analysis import analyze_message, analyze_sentiment, extract_entities
from chatbot.phishing_detector import check_url, extract_url_features
from chatbot.response_engine import get_answer


class NLPTests(unittest.TestCase):
    def test_sentiment_positive_and_negative(self):
        self.assertEqual(analyze_sentiment("This is great and safe")["label"], "positive")
        self.assertEqual(analyze_sentiment("I am worried about this scam")["label"], "negative")
        self.assertEqual(analyze_sentiment("Please explain this")["label"], "neutral")

    def test_entity_extraction(self):
        entities = extract_entities(
            "I received an OTP at https://example.com and email help@example.org from Paytm."
        )
        labels = {item["label"] for item in entities}
        self.assertIn("URL", labels)
        self.assertIn("DOMAIN", labels)
        self.assertIn("EMAIL", labels)
        self.assertIn("OTP_REFERENCE", labels)
        self.assertIn("ORGANIZATION", labels)

    def test_analysis_shape(self):
        result = analyze_message("I am worried about a suspicious URL https://example.com")
        self.assertIn("sentiment", result)
        self.assertIn("entities", result)


class PhishingDetectorTests(unittest.TestCase):
    def test_feature_extraction(self):
        features = extract_url_features("https://google.com")
        self.assertEqual(features["has_https"], 1)
        self.assertEqual(features["tld"], "com")
        self.assertEqual(features["has_ip"], 0)

    def test_model_prediction_shape(self):
        result = check_url("https://google.com")
        self.assertTrue(result["ok"], result)
        self.assertIn(result["label"], {"likely_phishing", "likely_legitimate"})
        self.assertGreaterEqual(result["phishing_probability"], 0)
        self.assertLessEqual(result["phishing_probability"], 1)
        self.assertIn("warning", result)

    def test_invalid_url(self):
        result = check_url("not a url")
        self.assertFalse(result["ok"])

    def test_chatbot_checks_urls(self):
        answer = get_answer("Is https://google.com safe?")
        self.assertIn("URL Safety Check", answer)
        self.assertIn("automated model estimate", answer)


if __name__ == "__main__":
    unittest.main()
