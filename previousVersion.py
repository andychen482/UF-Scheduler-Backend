from flask import Flask, request, jsonify
from flask_cors import CORS

import json
import re
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import base64
from io import BytesIO

app = Flask(__name__)
CORS(app)


@app.route('/generate_graph', methods=['POST'])
def generate_graph():
    data = request.get_json()

    course_graph = CourseGraph()
    G = nx.DiGraph()

    selected_major = data['selectedMajorServ']
    taken_courses = data['selectedCoursesServ']

    for i in range(len(taken_courses)):
        course = taken_courses[i]
        if course[-1].isalpha():
            taken_courses[i] = course[:-1]

    for course in taken_courses:
        G.add_node(course)

    # time here 
    initiateList(course_graph, G, selected_major)
    # time here

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

    # Draw the entire graph including nodes, edges, labels, arrows, and text attributes
    nx.draw(G, pos, with_labels=True, node_size=scaling_factor if scaling_factor > 4000 else 4000, arrows=True, alpha=0.75, font_size=12, edge_color='white')

    # Highlight nodes for taken courses using a different color
    nx.draw_networkx_nodes(G, pos, nodelist=taken_courses, node_size=scaling_factor if scaling_factor > 4000 else 4000, node_color='g')

    figFile = BytesIO()
    plt.savefig(figFile, transparent=True, format='png', dpi=300)
    figFile.seek(0)
    figData_png = base64.b64encode(figFile.getvalue())

    image_base64 = str(figData_png)[2:-1]

    return jsonify({'image': image_base64})
    

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

                course_graph.add_edge(course_code_stripped, prereq_stripped)
                G.add_edge(prereq_stripped, course_code_stripped)  # Add directed edge to the graph

            course_graph.add_attribute(course_code, "deptName", dept_name)
            course_graph.add_attribute(course_code, "instructors", course.get("instructors"))


if __name__ == '__main__':
    #For server use
    # app.run(host='0.0.0.0', port=5000, debug=False)
    #For local use
    app.run(debug=True)