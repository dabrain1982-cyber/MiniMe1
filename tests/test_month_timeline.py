import unittest

from month_timeline import timeline_html


class TimelineTests(unittest.TestCase):
    def test_same_grid_for_both_series_and_safe_labels(self):
        rendered = timeline_html(['April <2026>', 'Mai 2026'], [100, -50], [0, 25],
                                 lambda value, force_sign=False: str(value))
        self.assertEqual(rendered.count('repeat(2,minmax(140px,1fr))'), 2)
        self.assertIn('April &lt;2026&gt;', rendered)
        self.assertIn('background:#d65754', rendered)
        self.assertIn('requestAnimationFrame(latest)', rendered)

    def test_zero_values_have_valid_geometry(self):
        rendered = timeline_html(['April'], [0], [0], lambda value, **kwargs: '0,00 €')
        self.assertNotIn('nan', rendered)
        self.assertIn('height:0.0px', rendered)
