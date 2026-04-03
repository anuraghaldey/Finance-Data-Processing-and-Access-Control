"""Unit tests for Trie (Prefix Tree) search index."""

import pytest

from app.utils.search import SearchTrie, tokenize_description


@pytest.fixture
def trie():
    t = SearchTrie()
    t.insert('Salary', source='category')
    t.insert('Sales', source='category')
    t.insert('Salon expense', source='keyword')
    t.insert('Rent', source='category')
    t.insert('Restaurant', source='tag')
    return t


class TestTrie:
    def test_prefix_search(self, trie):
        results = trie.search_prefix('sal')
        words = [r['word'] for r in results]
        assert 'Salary' in words
        assert 'Sales' in words
        assert 'Salon expense' in words
        assert 'Rent' not in words

    def test_exact_match(self, trie):
        results = trie.search_prefix('Rent')
        assert len(results) == 1
        assert results[0]['word'] == 'Rent'

    def test_no_match(self, trie):
        results = trie.search_prefix('xyz')
        assert results == []

    def test_empty_prefix(self, trie):
        results = trie.search_prefix('')
        assert results == []

    def test_case_insensitive(self, trie):
        results = trie.search_prefix('SAL')
        assert len(results) == 3

    def test_max_results(self, trie):
        results = trie.search_prefix('', max_results=2)
        assert len(results) <= 2

    def test_source_tracking(self, trie):
        results = trie.search_prefix('Res')
        assert results[0]['source'] == 'tag'
        assert results[0]['word'] == 'Restaurant'

    def test_insert_and_search(self, trie):
        trie.insert('Subscription', source='category')
        results = trie.search_prefix('Sub')
        assert len(results) == 1

    def test_delete(self, trie):
        assert trie.size == 5
        trie.delete('Rent')
        assert trie.size == 4
        results = trie.search_prefix('Rent')
        assert results == []

    def test_delete_nonexistent(self, trie):
        result = trie.delete('Nonexistent')
        assert result is False
        assert trie.size == 5

    def test_short_words_ignored(self):
        t = SearchTrie()
        t.insert('a', source='keyword')
        t.insert('ab', source='keyword')  # len < 2 but insert checks >= 2
        assert t.size == 1  # 'a' ignored, 'ab' kept


class TestTokenizer:
    def test_basic_tokenization(self):
        tokens = tokenize_description('Monthly salary payment from company')
        assert 'monthly' in tokens
        assert 'salary' in tokens
        assert 'payment' in tokens
        assert 'company' in tokens
        assert 'from' not in tokens  # stop word

    def test_stop_words_removed(self):
        tokens = tokenize_description('This is a test of the system')
        assert 'test' in tokens
        assert 'system' in tokens
        assert 'this' not in tokens
        assert 'the' not in tokens

    def test_empty_input(self):
        assert tokenize_description('') == []
        assert tokenize_description(None) == []

    def test_short_words_excluded(self):
        tokens = tokenize_description('I am ok but fine')
        assert 'fine' in tokens
        assert 'ok' not in tokens  # len < 3
