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

    def find(self, prefix, limit):
        node = self
        for ch in prefix:
            if ch not in node.children:
                return []
            node = node.children[ch]
        return self._retrieve_courses(node, limit)

    def _retrieve_courses(self, node, limit):
        if limit[0] <= 0:
            return []
        courses = []
        if node.end_of_word:
            num_courses = len(node.courses)
            courses.extend(node.courses[:limit[0]])
            limit[0] -= num_courses
        for child in node.children.values():
            if limit[0] > 0:
                courses.extend(self._retrieve_courses(child, limit))
        return courses
