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


@app.route('/generate_a_list', methods=['POST'])
def generate_a_list():
  data = request.get_json()

  course_graph = CourseGraph()
  G = nx.DiGraph()

  selected_major = data['selectedMajorServ']
  taken_courses = data['selectedCoursesServ']

  for course in taken_courses:
    G.add_node(course)

  timeBefore = time.time()
  initiateList(course_graph, G, selected_major)
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


class CourseGraph:
  def __init__(self):
    self.adj_list = {}
    self.course_attributes = {}

  def add_edge(self, course_code, neighbor_code):
    if course_code not in self.adj_list:
      self.adj_list[course_code] = set()
    self.adj_list[course_code].add(neighbor_code)

  def add_attribute(self, course_code, attribute_name, attribute_value):
    if course_code not in self.course_attributes:
      self.course_attributes[course_code] = {}
    self.course_attributes[course_code][attribute_name] = attribute_value

  def get_attribute(self, course_code, attribute_name):
    if course_code in self.course_attributes:
      return self.course_attributes[course_code].get(attribute_name)

  def get_neighbors(self, course_code):
    return list(self.adj_list.get(course_code, set()))

  def find_courses_by_attribute(self, attribute_name, attribute_value):
    matching_courses = []
    for course_code, attributes in self.course_attributes.items():
      if attribute_name in attributes and attributes[attribute_name] == attribute_value:
        matching_courses.append(course_code)
    return matching_courses


def clean_prereq(prerequisites):
  # Use regular expression to find course codes in the prerequisites string
  pattern = r'[A-Z]{3}\s\d{4}'
  course_codes = re.findall(pattern, prerequisites)
  return course_codes


def initiateList(course_graph, G, selected_major):
  with open("doc/summer.json") as f1:
    data1 = json.load(f1)

  for course in data1:
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
          course_graph.add_edge(course_code_stripped, prereq_stripped)
          G.add_edge(prereq_stripped, course_code_stripped)  # Add directed edge to the graph

      course_graph.add_attribute(course_code, "deptName", dept_name)
      course_graph.add_attribute(course_code, "instructors", course.get("instructors"))

@app.route('/generate_a_matrix', methods=['POST'])
def generate_a_matrix():
  data = request.get_json()
  file = "doc/summer.json"

  other_course_graph = set()

  timeBefore = time.time()
  process_data(file, other_course_graph)

  other_selected_major = data['selectedMajorServ']
  other_taken_courses = data['selectedCoursesServ']

  dept = find_department_by_name(other_course_graph, other_selected_major)
  S = nx.DiGraph()

  for course in other_taken_courses:
    S.add_node(course)

  dept.remove_non_courses()
  print_department_courses(other_course_graph, S, dept.name)

  timeAfter = time.time()
  elapsedTime = round(timeAfter - timeBefore, 3)
  # Set up the plot
  plt.figure(figsize=(16, 16))
  try:
    for layer, nodes in enumerate(nx.topological_generations(S)):
      # `multipartite_layout` expects the layer as a node attribute, so add the
      # numeric layer value as a node attribute
      for node in nodes:
        S.nodes[node]["layer"] = layer
    pos = nx.multipartite_layout(S, subset_key="layer", scale=5.0)
  except:
    pos = nx.spring_layout(S, k=1.25)

  # Get the number of nodes in the graph
  num_nodes = S.number_of_nodes()

  # Calculate the scaling factor: inverse of the number of nodes
  scaling_factor = (100000.0 / num_nodes) if num_nodes != 0 else 100000.0

  if scaling_factor > 8000:
    scaling_factor = 8000

  # Draw the entire graph including nodes, edges, labels, arrows, and text attributes
  nx.draw(S, pos, with_labels=True, node_color='#0021A5', node_size=scaling_factor if scaling_factor > 3500 else 3500, arrows=True, alpha=0.75, font_size=12,
          edge_color='white', font_color='white', font_weight='bold', font_family='monospace')

  # Highlight nodes for taken courses using a different color
  nx.draw_networkx_nodes(S, pos, nodelist=other_taken_courses, node_size=scaling_factor if scaling_factor > 3500 else 3500, node_color='#FA4616', edgecolors='white', linewidths=2.0)

  figFile = BytesIO()
  plt.savefig(figFile, transparent=True, format='png', dpi=300)
  figFile.seek(0)
  figData_png = base64.b64encode(figFile.getvalue())

  image_base64 = str(figData_png)[2:-1]

  return jsonify({'otherImage': image_base64, 'otherTime': elapsedTime})


class Course:
  def __init__(self, code, description, name, dept_name, pre_req=None):
    self.code = code
    self.description = description
    self.name = name
    self.dept_name = dept_name
    self.pre_req = pre_req if pre_req is not None else []

  def __str__(self):
    return f"Course Code: {self.code}\nName: {self.name}\nDescription: {self.description}\n" \
           f"Department: {self.dept_name}\nPrerequisites: {self.pre_req}\n"

  def __eq__(self, other):
    return self.code == other.code and self.description == other.description and self.name == other.name

  def __hash__(self):
    return hash((self.code, self.description, self.name))

class DirectedGraph:
  def __init__(self):
    self.graph = {}

  def add_node(self, node):
    if node not in self.graph:
      self.graph[node] = []

  def add_edge(self, from_node, to_node):
    self.add_node(from_node)
    self.add_node(to_node)

    if to_node not in self.graph[from_node]:
      self.graph[from_node].append(to_node)

  def get_neighbors(self, node):
    return self.graph.get(node, [])

class Department:
  def __init__(self, name):
    self.name = name
    self.graph = DirectedGraph()

  def __eq__(self, other):
    return self.name == other.name

  def __hash__(self):
    return hash(self.name)

  def remove_non_courses(self):
    nodes_to_remove = []

    for node in self.graph.graph:
      if not isinstance(node, Course):
        nodes_to_remove.append(node)

    # Remove the nodes from the graph
    for node in nodes_to_remove:
      self.graph.graph.pop(node)

def extract_classes(input_str):
  pattern = r'\b[A-Z]+ \d{4}[A-Z]?[L]?\b'  # Regular expression pattern to match course codes
  classes = re.findall(pattern, input_str)
  return classes

def process_data(directory, department_set):
  with open(directory) as file:
    data = json.load(file)

  for course in data:
    for section in course['sections']:
      department_set.add(Department(section['deptName']))

  course_set = set()
  dept_name = ''

  for course in data:

    code = course['code']
    description = course['description']
    name = course['name']
    pre_req = extract_classes(course['prerequisites'])
    pre_req = remove_spaces_from_pre_req(pre_req)
    # print(pre_req)
    for section in course['sections']:
      dept_name = section['deptName']
      break

    course_set.add(Course(code, description, name, dept_name, pre_req))

  for department in department_set:
    for element in course_set:
      if element.dept_name == department.name:
        department.graph.add_node(element)

def find_course_by_code(course_code, department_set):
  for department in department_set:
    for course in department.graph.graph:

      if course.code == course_code:
        return course
  return None

def remove_spaces_from_pre_req(pre_req):
  # Loop through the pre_req list and remove spaces from course codes
  pre_req = [course_code.replace(" ", "") for course_code in pre_req]
  return pre_req

def find_department_by_name(department_set, name):
  for department in department_set:
    if department.name == name:
      return department
  return None  # If department with the given name is not found in the set

def add_edges_for_prerequisites(department):
  # Initialize a queue and a set for uniqueness
  course_queue = queue.Queue()
  unique_elements = set()

  def add_unique_to_queue(target):
    if target not in unique_elements:
      course_queue.put(target)
      unique_elements.add(target)

  if department:
    for course in department.graph.graph:
      print(course)

  add_unique_to_queue(1)
  add_unique_to_queue(2)
  add_unique_to_queue(3)
  add_unique_to_queue(1)  # This will not be added since 1 is already in the queue

  while not course_queue.empty():
    item = course_queue.get()
    print(item)

def bfs_pre_req_traversal(graph, department_set, start_course_code):
  visited = set()
  q = queue.Queue()
  final_set = set()

  # Find the starting course node based on the given course code
  start_course_node = None
  for course_node in graph.graph.graph:
    if course_node.code == start_course_code:
      start_course_node = course_node
      break

  if not start_course_node:
    print(f"Course with code {start_course_code} not found.")
    return

  # Add the starting course node to the queue and mark it as visited
  q.put(start_course_node)
  visited.add(start_course_node)

  # print("BFS Traversal for Pre-requisites:")
  while not q.empty():
    current_course_node = q.get()
    final_set.add(current_course_node)
    # print(current_course_node.code)

    # Explore the pre_req courses of the current course node
    for pre_req_course in current_course_node.pre_req:
      # Find the course node based on the pre_req course code
      pre_req_course_node = find_course_by_code(pre_req_course, department_set)

      if pre_req_course_node and pre_req_course_node not in visited:
        q.put(pre_req_course_node)
        visited.add(pre_req_course_node)

  return final_set

def add_edges_by_dep(department_set, dept_name, given_set):
  dept_to_iter = find_department_by_name(department_set, dept_name.name)
  for course in given_set:
    dept_to_iter.graph.add_node(course)

  for course in given_set:
    for code in course.pre_req:
      dept_to_iter.graph.add_edge(code, course)


def print_department_courses(department_set, network_graph, department_name):
  department = find_department_by_name(department_set, department_name)
  if department:
    for course in department.graph.graph:
      course_code = course.code
      for pre_req in course.pre_req:
        network_graph.add_edge(pre_req, course_code)

if __name__ == '__main__':
  # For server use
  app.run(host='0.0.0.0', port=5000, debug=False)
  # For local use
  # app.run(debug=True)