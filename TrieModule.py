class TrieNode:
    def __init__(self):
        self.children = {}
        self.end_of_word = False
        self.courses = []

    def add(self, word, course):
        node = self
        for ch in word:
            if ch not in node.children:
                node.children[ch] = TrieNode()
            node = node.children[ch]
        node.end_of_word = True
        node.courses.append(course)

    def find(self, prefix):
        node = self
        for ch in prefix:
            if ch not in node.children:
                return []
            node = node.children[ch]
        return node.courses
