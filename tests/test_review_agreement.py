"""Reviewer-agreement arithmetic on small constructed label sets."""
import tempfile
import unittest
from pathlib import Path

from review_agreement import LABELS, agreement, read_labels

M, A, U = LABELS


class ReviewAgreementTests(unittest.TestCase):
    def test_identical_labels_give_full_agreement(self):
        first = {'c1': M, 'c2': A, 'c3': U, 'c4': U}
        result = agreement(first, dict(first))
        self.assertEqual((result['agreeing_cases'], result['cohen_kappa']), (4, 1.0))
        self.assertEqual(result['needs_adjudication'], {})

    def test_kappa_matches_a_hand_computed_example(self):
        first = {'c1': M, 'c2': M, 'c3': A, 'c4': U}
        second = {'c1': M, 'c2': U, 'c3': A, 'c4': U}
        result = agreement(first, second)
        # observed 3/4; chance (2*1 + 1*1 + 1*2) / 16 = 5/16; kappa = (0.75 - 0.3125) / 0.6875
        self.assertEqual(result['agreeing_cases'], 3)
        self.assertAlmostEqual(result['cohen_kappa'], 0.636, places=3)
        self.assertEqual(result['needs_adjudication'], {'c2': [M, U]})
        self.assertEqual(result['cross_table_rows_first_columns_second'][M][U], 1)

    def test_different_case_lists_are_refused(self):
        with self.assertRaises(ValueError):
            agreement({'c1': M}, {'c2': M})

    def test_unknown_label_in_a_file_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'labels.csv'
            path.write_text('"case_id","formal_label"\n"c1","maybe"\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                read_labels(path)


if __name__ == '__main__':
    unittest.main()
