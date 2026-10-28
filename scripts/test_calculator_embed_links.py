from unittest import TestCase, main
from build_calculator_embeds import outbound_links

class EmbedLinks(TestCase):
    def test_leave_in_page_controls_and_preserve_link_relationships(self):
        source='<a href="#inputs">Inputs</a><a href="https://example.org" rel="license" target="_self">Source</a><a href="/about.html">Author</a>'
        result=outbound_links(source)
        self.assertIn('<a href="#inputs">Inputs</a>',result)
        self.assertIn('target="_blank" rel="license noopener"',result)
        self.assertIn('<a href="/about.html" target="_blank" rel="noopener">',result)
        self.assertEqual(outbound_links(result),result)

if __name__=='__main__':main()
