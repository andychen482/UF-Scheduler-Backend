from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import glob
import sqlite3
import re
import networkx as nx
import gc
import os

app = Flask(__name__)
CORS(app, origins=[
    'http://ufscheduler.com',
    'https://ufscheduler.com',
    'http://www.ufscheduler.com',
    'https://www.ufscheduler.com',
    'http://localhost:3000'
])

# -------------------------------------------------------------------
# 1. Locate and load your course JSON file
# -------------------------------------------------------------------
json_file = glob.glob('courses/*_final.json')[0]
with open(json_file) as f:
    all_courses = json.load(f)

# -------------------------------------------------------------------
# 2. Create/Open SQLite Database and Create FTS Table with Prefixes
# -------------------------------------------------------------------
DB_NAME = 'courses.db'

def get_connection():
    """
    Returns a connection to the SQLite database.
    """
    return sqlite3.connect(DB_NAME)

def init_db():
    """
    Initializes the database and FTS table (with prefix support).
    Inserts all courses if the table is empty.
    """
    conn = get_connection()
    cur = conn.cursor()

    # Enable WAL mode (optional) to improve concurrency
    cur.execute("PRAGMA journal_mode=WAL;")

    # Create an FTS5 virtual table with prefix indexes on lengths 2, 3, and 4.
    # Adjust these lengths depending on how deep you want the prefix matching.
    # For example, prefix='1 2 3' would allow matching from the first character onwards.
    cur.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS courses_fts
        USING fts5(
            code,
            codeWithSpace,
            name,
            description,
            prerequisites,
            instructors,
            prefix='2 3 4'
        )
    ''')

    # Check if the table is empty; if so, insert data
    row_count = cur.execute('SELECT count(*) FROM courses_fts;').fetchone()[0]
    if row_count == 0:
        # Insert all course data
        for course in all_courses:
            code = course['code']
            codeWithSpace = course['codeWithSpace']
            name = course.get('name', '')
            description = course.get('description', '')
            prerequisites = course.get('prerequisites', '')

            # Collect all instructor names in one string
            instructor_names = []
            for section in course.get('sections', []):
                for inst in section.get('instructors', []):
                    instructor_names.append(inst.get('name', ''))
            instructors_joined = ' '.join(instructor_names)

            cur.execute('''
                INSERT INTO courses_fts (code, codeWithSpace, name, description, prerequisites, instructors)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (code, codeWithSpace, name, description, prerequisites, instructors_joined))

        conn.commit()

    conn.close()

# Initialize the database once on startup
init_db()

# -------------------------------------------------------------------
# 3. Maintain references for generating graph, etc.
# -------------------------------------------------------------------
course_code_to_course = {course['code']: course for course in all_courses}
course_code_to_dept_name = {
    course['code']: course.get('sections', [{}])[0].get("deptName", "")
    for course in all_courses
}

del all_courses  # free memory
gc.collect()

# -------------------------------------------------------------------
# 4. Search Endpoint (with Prefix Matching)
# -------------------------------------------------------------------
@app.route("/api/get_courses", methods=['POST'])
def get_courses():
    """
    Receives a JSON body with:
      - searchTerm: the query string
      - itemsPerPage: number of items per page
      - startFrom: offset for pagination
    Returns a JSON list of matched courses, with prefix matching.
    """
    data = request.json
    searchTerm = data.get('searchTerm', '').strip()
    itemsPerPage = data.get('itemsPerPage', 20)
    startFrom = data.get('startFrom', 0)

    if not searchTerm:
        return jsonify([])

    # Split on whitespace, then append '*' for prefix matching on each term
    # Example: "prog fun" -> "prog*" "fun*"
    terms = searchTerm.split()
    prefix_terms = [term + '*' for term in terms]
    # Join them with spaces so FTS interprets them as an AND query by default
    # i.e. must match each prefix term
    fts_query = ' '.join(prefix_terms)

    # Connect to SQLite and perform an FTS query
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # CASE expression to prioritize exact matches on codeWithSpace
    query = '''
        SELECT
            code,
            codeWithSpace,
            name,
            description,
            prerequisites,
            instructors,
            bm25(courses_fts) AS rank,
            CASE 
                WHEN codeWithSpace = :exactSearch THEN 0 
                ELSE 1 
            END AS top_sort
        FROM courses_fts
        WHERE courses_fts MATCH :ftsQuery
        ORDER BY top_sort, rank
        LIMIT :limit
        OFFSET :offset
    '''

    rows = cur.execute(query, {
        'exactSearch': searchTerm,
        'ftsQuery': fts_query,
        'limit': itemsPerPage,
        'offset': startFrom
    }).fetchall()

    results = []
    for row in rows:
        code = row['code']
        # Reconstruct the full course object from your dictionary
        course_obj = course_code_to_course.get(code, {})
        results.append(course_obj)

    conn.close()
    return jsonify(results)

# -------------------------------------------------------------------
# 5. /generate_a_list (same as your original)
# -------------------------------------------------------------------
@app.route('/generate_a_list', methods=['POST'])
def generate_a_list():
    data = request.get_json()
    G = nx.DiGraph()

    selected_major = data['selectedMajorServ']
    taken_courses = data['selectedCoursesServ']
    formatted_taken_courses = [
        format_course_code(course.rstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ '))
        for course in taken_courses
    ]

    # Add each taken course as a node
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

    # Filter courses by department name
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

# -------------------------------------------------------------------
# 6. Optional: run the app
# -------------------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True)
