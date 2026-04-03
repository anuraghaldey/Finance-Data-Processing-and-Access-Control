"""
Trie (Prefix Tree) for search index autocomplete.

Builds vocabulary from categories + tags + top description keywords.
Provides O(k) prefix matching where k = query length.

DB alternative (ILIKE 'prefix%') requires index scans and network
roundtrips per keystroke. The Trie serves results from memory.

Memory: capped at ~1500 vocabulary entries → ~500 KB worst case.
"""

import re
from collections import Counter

# Common stop words to exclude from description tokenization
STOP_WORDS = frozenset({
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'can', 'shall', 'to', 'of', 'in', 'for',
    'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through', 'during',
    'before', 'after', 'above', 'below', 'and', 'but', 'or', 'nor', 'not',
    'so', 'yet', 'both', 'either', 'neither', 'each', 'every', 'all',
    'any', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'only',
    'own', 'same', 'than', 'too', 'very', 'just', 'because', 'if', 'then',
    'this', 'that', 'these', 'those', 'it', 'its', 'i', 'me', 'my', 'we',
    'our', 'you', 'your', 'he', 'him', 'his', 'she', 'her', 'they', 'them',
})

MAX_KEYWORDS = 1000  # Cap description keywords to top 1000 most frequent


class TrieNode:
    __slots__ = ['children', 'is_end', 'word', 'source']

    def __init__(self):
        self.children = {}
        self.is_end = False
        self.word = None
        self.source = None  # 'category', 'tag', or 'keyword'


class SearchTrie:
    """Prefix tree for autocomplete search across categories, tags, and keywords."""

    def __init__(self):
        self.root = TrieNode()
        self._word_count = 0

    def insert(self, word, source='keyword'):
        """Insert a word into the trie. O(k) where k = len(word)."""
        if not word or len(word) < 2:
            return

        node = self.root
        normalized = word.lower().strip()

        for char in normalized:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]

        if not node.is_end:
            self._word_count += 1
        node.is_end = True
        node.word = word  # Preserve original casing
        node.source = source

    def search_prefix(self, prefix, max_results=10):
        """
        Find all words matching a prefix. O(k + m) where k = prefix length,
        m = number of results collected.
        Returns list of {'word': str, 'source': str}.
        """
        if not prefix:
            return []

        node = self.root
        normalized = prefix.lower().strip()

        # Traverse to the prefix node
        for char in normalized:
            if char not in node.children:
                return []
            node = node.children[char]

        # Collect all words under this prefix
        results = []
        self._collect(node, results, max_results)
        return results

    def _collect(self, node, results, max_results):
        """DFS to collect all complete words under a node."""
        if len(results) >= max_results:
            return

        if node.is_end:
            results.append({'word': node.word, 'source': node.source})

        for char in sorted(node.children.keys()):
            if len(results) >= max_results:
                return
            self._collect(node.children[char], results, max_results)

    def delete(self, word):
        """Remove a word from the trie. O(k)."""
        if not word:
            return False
        return self._delete(self.root, word.lower().strip(), 0)

    def _delete(self, node, word, depth):
        if depth == len(word):
            if not node.is_end:
                return False
            node.is_end = False
            node.word = None
            node.source = None
            self._word_count -= 1
            return len(node.children) == 0

        char = word[depth]
        if char not in node.children:
            return False

        should_delete = self._delete(node.children[char], word, depth + 1)

        if should_delete:
            del node.children[char]
            return not node.is_end and len(node.children) == 0

        return False

    @property
    def size(self):
        return self._word_count


def tokenize_description(text):
    """Extract meaningful keywords from a description."""
    if not text:
        return []
    words = re.findall(r'[a-zA-Z]{3,}', text.lower())
    return [w for w in words if w not in STOP_WORDS]


# Singleton
_search_trie = None


def get_search_trie():
    global _search_trie
    if _search_trie is None:
        _search_trie = SearchTrie()
    return _search_trie


def rebuild_search_trie(records):
    """Rebuild trie from DB records on startup."""
    global _search_trie
    _search_trie = SearchTrie()

    # Collect all keywords for frequency analysis
    keyword_counter = Counter()

    for r in records:
        # Categories (all included)
        _search_trie.insert(r.category, source='category')

        # Tags (all included)
        if r.tags:
            for tag in r.tags:
                _search_trie.insert(tag, source='tag')

        # Description keywords (counted for top-N selection)
        if r.description:
            for kw in tokenize_description(r.description):
                keyword_counter[kw] += 1

    # Insert only top N most frequent keywords
    for kw, _ in keyword_counter.most_common(MAX_KEYWORDS):
        _search_trie.insert(kw, source='keyword')

    return _search_trie
