import unittest
from app.utils.validators import normalize_url

class TestValidators(unittest.TestCase):
    
    def test_normalize_url_with_scheme(self):
        """Test URL normalization with existing scheme."""
        url = "https://example.com/dns-query/"
        result = normalize_url(url)
        self.assertEqual(result, "https://example.com/dns-query")
    
    def test_normalize_url_without_scheme(self):
        """Test URL normalization without scheme."""
        url = "example.com/dns-query"
        result = normalize_url(url)
        self.assertEqual(result, "https://example.com/dns-query")
    
    def test_normalize_url_trailing_slash(self):
        """Test removal of trailing slash."""
        url = "https://example.com/dns-query/"
        result = normalize_url(url)
        self.assertFalse(result.endswith("/"))

if __name__ == '__main__':
    unittest.main()
