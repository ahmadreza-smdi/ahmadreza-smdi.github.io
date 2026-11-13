import unittest
from answer_resources import DESCRIPTION, PERSON, PORTRAIT, markdown, machine_head
from check_answer_resources import check_date, check_facts, check_person, check_robots, equal

class AnswerResources(unittest.TestCase):
    def test_unpublished_catalogue_sentence_fails(self):
        with self.assertRaises(ValueError):
            equal('Published. Invented detail.', 'Published.', 'catalogue drift')

    def test_mirror_rejects_changed_quotation(self):
        source='<main><h1>About</h1><p>Published words.</p></main>'
        with self.assertRaises(ValueError):
            equal('# About\n\nChanged words.\n',markdown(source,'about.html'),'mirror drift')

    def test_person_cannot_point_at_another_photo_or_identity(self):
        image={'@type':'ImageObject','@id':'https://a-samadi.com/#portrait','url':PORTRAIT,
               'contentUrl':PORTRAIT,'name':'Ahmadreza Samadi','caption':'Ahmadreza Samadi in a dark suit'}
        person={'@id':PERSON,'disambiguatingDescription':DESCRIPTION,'image':image}
        check_person(person)
        for replacement in ({'@id':'#someone'}, {'image':{'url':'other.jpg'}},{'disambiguatingDescription':'unrelated executive'}):
            with self.assertRaises(ValueError):
                check_person({**person,**replacement})

    def test_sitemap_cannot_postdate_commit(self):
        with self.assertRaises(ValueError):
            check_date('2026-11-13T01:00:00+00:00','2026-11-13T01:00:00+03:30')

    def test_source_missing_dubai_fails(self):
        with self.assertRaises(ValueError):
            check_facts('Ahmadreza Samadi', ['name','dubai'])

    def test_search_block_fails(self):
        with self.assertRaises(ValueError):
            check_robots('User-agent: OAI-SearchBot\nDisallow: /\n\nUser-agent: *\nAllow: /\nContent-Signal: search=yes, ai-input=yes')

    def test_nested_lists_and_excluded_operator_paragraph(self):
        source='<main><h1>Biography</h1><p>Retain <strong>these</strong> words.</p><p>Restricted <a href="/work/royal-abraj.html#raia-title">details</a>.</p></main>'
        self.assertEqual(markdown(source,'fa/about.html'),'# Biography\n\nRetain these words.\n')

if __name__=='__main__':
    unittest.main()
