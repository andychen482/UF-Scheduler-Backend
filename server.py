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
CORS(app)

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

  timeBefore = time.time()
  initiateList(G, selected_major)
  timeAfter = time.time()
  elapsedTime = round(timeAfter - timeBefore, 3)

  # Set up the plot
  plt.figure(figsize=(16, 16))
  try:
    for layer, nodes in enumerate(nx.topological_generations(G)):
      # `multipartite_layout` expects the layer as a node attribute, so add the
      # numeric layer value as a node attribute
      for node in nodes:
        G.nodes[node]["layer"] = layer
    pos = nx.multipartite_layout(G, subset_key="layer", scale=5.0)
  except:
    pos = nx.spring_layout(G, k=1.25)

  # Get the number of nodes in the graph
  num_nodes = G.number_of_nodes()

  # Calculate the scaling factor: inverse of the number of nodes
  scaling_factor = (100000.0 / num_nodes) if num_nodes != 0 else 100000.0

  if scaling_factor > 8000:
    scaling_factor = 8000

  # Draw the entire graph including nodes, edges, labels, arrows, and text attributes
  nx.draw(G, pos, with_labels=True, node_color='#0021A5', node_size=scaling_factor if scaling_factor > 3500 else 3500, arrows=True, alpha=0.75, font_size=12,
          edge_color='white', font_color='white', font_weight='bold', font_family='monospace')

  # Highlight nodes for taken courses using a different color
  nx.draw_networkx_nodes(G, pos, nodelist=taken_courses, node_size=scaling_factor if scaling_factor > 3500 else 3500, node_color='#FA4616', edgecolors='white', linewidths=2.0)

  figFile = BytesIO()
  plt.savefig(figFile, transparent=True, format='png', dpi=300)
  figFile.seek(0)
  figData_png = base64.b64encode(figFile.getvalue())

  image_base64 = str(figData_png)[2:-1]

  return jsonify({'image': image_base64, 'time': elapsedTime})

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


if __name__ == '__main__':
  # For server use
  app.run(host='0.0.0.0', port=5000, debug=False)
  # For local use
  # app.run(debug=True)