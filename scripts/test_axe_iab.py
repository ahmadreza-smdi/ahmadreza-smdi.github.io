"""Receipts must represent an actual, complete, current scan; manual findings are not a pass on contrast."""
from copy import deepcopy
import unittest
from check_axe_iab import TAGS,VERSION,verify

class Gate(unittest.TestCase):
    def test_scope_and_failures(self):
        good=dict(format=1,axe=VERSION,inputs='one',tags=TAGS,results=[dict(path='index.html',version=VERSION,
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
if __name__=='__main__':unittest.main()
