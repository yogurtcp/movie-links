"""Check comparison membership and tie handling independently of the live catalog."""
import unittest
from rating_context import make_reference, context_for_title, midrank, load_reference


def row(kind, score, genres='Comedy', votes=50000):
    return {'title_type': kind, 'rating': str(score), 'genres': genres, 'votes': str(votes)}


class RatingContextTests(unittest.TestCase):
    def test_midrank_ties_and_extremes(self):
        hist = [0] * 101
        hist[60], hist[80] = 2, 1
        self.assertAlmostEqual(midrank(hist, 60)['percentile'], 100 / 3, places=4)
        self.assertAlmostEqual(midrank(hist, 80)['percentile'], 250 / 3, places=4)
        self.assertEqual(midrank(hist, 60)['equal_rated'], 2)
        self.assertIsNone(midrank([0] * 101, 80))
        self.assertEqual(midrank(hist, 60)['lower_rated'], 0)

    def test_all_tied_titles_have_middle_rank(self):
        hist = [0] * 101
        hist[75] = 12
        self.assertEqual(midrank(hist, 75)['percentile'], 50)

    def test_population_before_rating_cutoff_and_inclusive_votes(self):
        ref = make_reference([row('movie', 4), row('movie', 8), row('movie', 10, votes=49999),
                              row('tvMovie', 9)], '2026-10-15')
        self.assertEqual(ref['groups']['movies']['population'], 2)
        self.assertEqual(ref['groups']['movies']['histogram'][40], 1)
        context = context_for_title({'title_type': 'movie', 'rating': 8, 'num_votes': 50000, 'genres': ['Comedy']}, ref)
        self.assertEqual(context['overall']['percentile'], 75)
        self.assertIsNone(context_for_title({'title_type': 'movie', 'rating': 8, 'num_votes': 49999}, ref))

    def test_series_and_miniseries_pooled_separately_from_movies(self):
        ref = make_reference([row('movie', 10), row('tvSeries', 8), row('tvMiniSeries', 6)], '2026-10-15')
        context = context_for_title({'title_type': 'tvMiniSeries', 'rating': 6, 'num_votes': 50000, 'genres': ['Comedy']}, ref)
        self.assertEqual(context['overall']['population'], 2)
        self.assertEqual(context['overall']['percentile'], 25)
        self.assertEqual(context['group'], 'tv')

    def test_overlapping_genres_are_separate_not_averaged(self):
        ref = make_reference([row('movie', 6, 'Romance,Comedy,Romance'), row('movie', 8, 'Comedy'),
                              row('movie', 4, 'Adventure')], '2026-10-15')
        context = context_for_title({'title_type': 'movie', 'rating': 6, 'num_votes': 900000, 'genres': ['Romance','Comedy']}, ref)
        ranks = {g['genre']: g for g in context['genres']}
        self.assertEqual(context['overall']['percentile'], 50)
        self.assertEqual(ranks['Romance']['population'], 1)
        self.assertEqual(ranks['Romance']['percentile'], 50)
        self.assertEqual(ranks['Comedy']['percentile'], 25)
        self.assertTrue(ranks['Comedy']['small_group'])

    def test_small_group_threshold_and_equal_title_weight(self):
        rows = [row('movie', 7, votes=50000 if i < 15 else 1000000) for i in range(30)]
        ref = make_reference(rows, '2026-10-15')
        context = context_for_title({'title_type': 'movie', 'rating': 7, 'num_votes': 50000, 'genres': ['Comedy']}, ref)
        self.assertEqual(context['overall']['percentile'], 50)
        self.assertFalse(context['genres'][0]['small_group'])

    def test_checked_in_reference_matches_original_eligible_population(self):
        ref = load_reference()
        self.assertEqual(ref['groups']['movies']['population'], 4674)
        self.assertEqual(ref['groups']['tv']['population'], 721)
        for group in ref['groups'].values():
            self.assertEqual(sum(group['histogram']), group['population'])
            for genre in group['genres'].values():
                self.assertEqual(sum(genre['histogram']), genre['population'])
                self.assertLessEqual(genre['population'], group['population'])


if __name__ == '__main__':
    unittest.main()
