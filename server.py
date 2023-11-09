from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import re
import networkx as nx
from TrieModule import TrieNode

app = Flask(__name__)
CORS(app, origins=[
    'http://ufscheduler.com',
    'https://ufscheduler.com',
    'http://www.ufscheduler.com',
    'https://www.ufscheduler.com',
    'http://localhost:3000'
])

with open("courses/UF_Nov-09-2023_24_spring_clean.json") as f1:
    all_courses = json.load(f1)

course_trie = TrieNode()
for course in all_courses:
    code = course['code'].upper().replace(" ", "")
    course_trie.add(code, course)

# Preprocess all_courses once at the beginning
course_code_to_course = {course['code']: course for course in all_courses}
course_code_to_dept_name = {
    course['code']: course.get('sections', [{}])[0].get("deptName", "")
    for course in all_courses
}

del all_courses

import gc
gc.collect()


@app.route("/api/get_courses", methods=['POST'])
def get_courses():
    data = request.json
    searchTerm = data.get('searchTerm', '').replace(" ", "")
    itemsPerPage = data.get('itemsPerPage', 20)
    startFrom = data.get('startFrom', 0)

    filtered_courses = course_trie.find(searchTerm, [itemsPerPage + startFrom])
    paginated_courses = filtered_courses[startFrom:startFrom + itemsPerPage]

    return jsonify(paginated_courses)


@app.route('/generate_a_list', methods=['POST'])
def generate_a_list():
    data = request.get_json()
    G = nx.DiGraph()

    selected_major = data['selectedMajorServ']
    taken_courses = data['selectedCoursesServ']
    formatted_taken_courses = [format_course_code(course.rstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ ')) for course in taken_courses]

    for course in formatted_taken_courses:
        G.add_node(course)

    initiateList(G, selected_major)

    nodes = [
        {"data": {"id": node}, "classes": "selected" if node in formatted_taken_courses else "not_selected"}
        for node in G.nodes()
    ]
    edges = [{"data": {"source": edge[0], "target": edge[1]}} for edge in G.edges()]

    return jsonify({
        'nodes': nodes,
        'edges': edges
    })


def clean_prereq(prerequisites):
    pattern = r'[A-Z]{3}\s\d{4}'
    return re.findall(pattern, prerequisites)


def format_course_code(course):
    return course[:3] + '\n' + course[3:]


def initiateList(G, selected_major):
    if not selected_major:
        return

    # This is to filter courses by department name just once
    relevant_courses = {
        code for code, dept in course_code_to_dept_name.items()
        if selected_major in dept
    }

    for course_code in relevant_courses:
        course = course_code_to_course[course_code]
        prereq_list = clean_prereq(course.get("prerequisites", ""))
        
        course_code_formatted = format_course_code(course_code.rstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ '))
        for prereq in prereq_list:
            prereq_formatted = format_course_code(prereq.replace(" ", "").rstrip(' '))

            if course_code_formatted != prereq_formatted:
                G.add_edge(prereq_formatted, course_code_formatted)

# if __name__ == '__main__':
#     app.run(debug=True)
