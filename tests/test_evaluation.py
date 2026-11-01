import unittest
from evaluation.metrics import classification,binary_ranking,retrieval
class EvaluationTests(unittest.TestCase):
    def test_confusion_count_denominator_and_macro_f1(self):
        r=classification(['clean','damaged'],['clean','clean','damaged','damaged'],['clean','damaged','damaged','damaged'])
        self.assertEqual(r['confusion_matrix'],[[1,1],[0,2]]);self.assertEqual(r['accuracy'],.75);self.assertAlmostEqual(r['macro_f1'],(2/3+.8)/2)
    def test_missing_classes_and_unknown_predictions(self):
        self.assertEqual(classification(['a','b'],['a'],['a'])['missing_classes'],['b'])
        with self.assertRaises(ValueError):classification(['a'],['a'],['other'])
    def test_roc_ties_are_grouped(self):
        r=binary_ranking([1,0,1,0],[.5,.5,.5,.5]);self.assertEqual(r['roc_auc'],.5);self.assertEqual(r['average_precision'],.5)
    def test_perfect_and_reversed_scores(self):
        self.assertEqual(binary_ranking([0,1],[0,1])['roc_auc'],1)
        self.assertEqual(binary_ranking([0,1],[1,0])['roc_auc'],0)
        with self.assertRaises(ValueError):binary_ranking([1,1],[.2,.4])
    def test_retrieval_denominators_and_abstention(self):
        q=[{'id':'1','review_state':'approved','reviewer':'human','answerable':True,'relevant_chunk_ids':['gold']},{'id':'2','review_state':'approved','reviewer':'human','answerable':False,'relevant_chunk_ids':[]}]
        r=retrieval(q,{'1':['wrong','gold'],'2':[]});self.assertEqual(r['top1'],0);self.assertEqual(r['top3'],1);self.assertEqual(r['mrr'],.5);self.assertEqual(r['correct_abstentions'],1)
    def test_unreviewed_labels_and_missing_runs_cannot_be_scored(self):
        with self.assertRaises(ValueError):retrieval([{'id':'1','review_state':'pending'}],{'1':[]})
        with self.assertRaises(ValueError):retrieval([{'id':'1'}],{})
