"""Receipts must represent an actual, complete, current scan; manual findings are not a pass on contrast."""
from copy import deepcopy
import unittest
from check_axe_iab import EXT,TAGS,VERSION,verify

class Gate(unittest.TestCase):
    def test_scope_and_failures(self):
        good=dict(format=2,axe=VERSION,inputs='one',tags=TAGS,results=[dict(path='index.html',version=VERSION,
            passes=['document-title'],incomplete=[{'id':'color-contrast'}],violations=[])])
        self.assertEqual(verify(good,['index.html'],'one'),1)
        for change in ['stale','missing','duplicate','wrong-scope','findings','crashed','no-tests']:
            d=deepcopy(good)
            if change=='stale':d['inputs']='old'
            if change=='missing':d['results']=[]
            if change=='duplicate':d['results']*=2
            if change=='wrong-scope':d['tags']=['wcag2a']
            if change=='findings':d['results'][0]['violations']=[{'id':'image-alt'}]
            if change=='crashed':d['results'][0]['error']='no document'
            if change=='no-tests':d['results'][0]['passes']=[]
            with self.subTest(change=change), self.assertRaises(ValueError):verify(d,['index.html'],'one')
    def test_module_backed_study_requires_rendered_data(self):
        self.assertIn('.mjs', EXT)
        page = 'fa/studies/rent-own-2026/index.html'
        row = dict(path=page, version=VERSION, passes=['document-title'], incomplete=[], violations=[])
        receipt = dict(format=2, axe=VERSION, inputs='assets', tags=TAGS, results=[row])
        with self.assertRaisesRegex(ValueError, 'did not initialize'):
            verify(receipt, [page], 'assets')
        row['initializedWidget'] = 'rent-own-study'
        self.assertEqual(verify(receipt, [page], 'assets'), 0)

if __name__=='__main__':unittest.main()
