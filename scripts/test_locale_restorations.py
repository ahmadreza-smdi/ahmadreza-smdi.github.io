"""Guard against overwriting future manual copy when replaying parity patches."""
from unittest import TestCase, main
from build_locale_restorations import restore


class Restorations(TestCase):
    row = {'source': 'writing/example.html', 'before': '<p>Before.</p>', 'after': '<p>Restored.</p>'}

    def test_idempotent_and_preserves_surrounding_content(self):
        source = 'Header<p>Before.</p>Unrelated footer'
        result = restore(source, [self.row])
        self.assertEqual(result, 'Header<p>Restored.</p>Unrelated footer')
        self.assertEqual(restore(result, [self.row]), result)

    def test_unknown_and_duplicate_copy_fail_closed(self):
        for source in ('<p>New manual edit.</p>', '<p>Before.</p><p>Before.</p>'):
            with self.assertRaises(ValueError):
                restore(source, [self.row])


if __name__ == '__main__':
    main()
