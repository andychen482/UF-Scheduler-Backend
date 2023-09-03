import queue

from flask import Flask, request, jsonify
from flask_cors import CORS

import json
import re
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib
import time

matplotlib.use('Agg')
import base64
from io import BytesIO

app = Flask(__name__)
CORS(app, origins=['http://ufscheduler.com', 'https://ufscheduler.com', 'http://www.ufscheduler.com', 'https://www.ufscheduler.com', 'http://localhost:3000'])

with open("doc/Fall2023.json") as f1:
  all_courses = json.load(f1)

@app.route("/api/get_courses", methods=['POST'])
def get_courses():
    data = request.json
    searchTerm = data.get('searchTerm', '').upper().replace(" ", "")
    itemsPerPage = data.get('itemsPerPage', 20)
    startFrom = data.get('startFrom', 0)

    # Filter and paginate the data based on the provided criteria
    filtered_courses = [
        course for course in all_courses if course['code'].upper().startswith(searchTerm)
    ]
    paginated_courses = filtered_courses[startFrom:startFrom + itemsPerPage]

    return jsonify(paginated_courses)

@app.route('/generate_a_list', methods=['POST'])
def generate_a_list():
    data = request.get_json()

    G = nx.DiGraph()

    selected_major = data['selectedMajorServ']
    taken_courses = data['selectedCoursesServ']

    for course in taken_courses:
        G.add_node(course)

    initiateList(G, selected_major)

    # Extract nodes and edges for Cytoscape
    nodes = [{"data": {"id": node}, "classes": "selected" if node in taken_courses else "not_selected"} for node in G.nodes()]
    edges = [{"data": {"source": edge[0], "target": edge[1]}} for edge in G.edges()]

    return jsonify({
        'nodes': nodes,
        'edges': edges
    })

def clean_prereq(prerequisites):
  # Use regular expression to find course codes in the prerequisites string
  pattern = r'[A-Z]{3}\s\d{4}'
  course_codes = re.findall(pattern, prerequisites)
  return course_codes


def initiateList(G, selected_major):

  for course in all_courses:
    course_code = course.get("code")
    sections = course.get('sections', [])  # Get the sections list for each course
    dept_name = sections[0].get("deptName", "") if sections else ""  # First section is enough

    if selected_major in dept_name:  # Check if the selected major is in the department name
      prereq_list = clean_prereq(course.get("prerequisites", ""))

      for prereq in prereq_list:
        # Omit space, and letters at the end
        course_code_stripped = course_code.rstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ ')
        prereq_stripped = prereq.replace(" ", "").rstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ')

        if course_code_stripped != prereq_stripped:
          G.add_edge(prereq_stripped, course_code_stripped)  # Add directed edge to the graph


# if __name__ == '__main__':
#   # For server use
# #   app.run(host='0.0.0.0', port=5000, debug=False)
#   # For local use
#   app.run(debug=True)