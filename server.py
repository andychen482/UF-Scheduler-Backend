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
# 1. Locate and load all course JSON files corresponding to (_{year}_{term}_final.json)
#    Create a dictionary of code->course for each (year, term).
# -------------------------------------------------------------------

json_files = glob.glob('courses/*_final.json')
course_data_map = {}  # Dictionary keyed by (year, term) -> {code -> course}
course_dept_map = {}  # Dictionary keyed by (year, term) -> {code -> deptName}

def parse_year_term_from_filename(filename):
    """
    Parses the filename to extract the year and term.
    Assumes filename ends with something like: '_{year}_{term}_final.json'
    For example: 'UF_Feb-21-2025_25_fall_final.json' -> (year='25', term='fall')
    """
    # This is a simple approach; adapt to your file naming as needed.
    # We'll split on underscores and take indices from the end.
    parts = os.path.basename(filename).split('_')
    # e.g. ['UF', 'Feb-21-2025', '25', 'fall', 'final.json']
    # year might be parts[-3], term might be parts[-2] (depending on your naming)
    year = parts[-3]
    term = parts[-2]
    # strip off any file extension from term if needed, e.g. "fall_final.json" -> "fall"
    if 'final.json' in term:
        term = term.replace('final.json', '')
    return year, term

# -------------------------------------------------------------------
# 2. Create/Open SQLite Database(s) for each (year, term)
#    and Create FTS Table with Prefixes, then insert data.
# -------------------------------------------------------------------

def get_connection(db_name):
    """
    Returns a connection to the given SQLite database.
    """
    return sqlite3.connect(db_name)

def init_db_for_file(json_path):
    """
    - Parses (year, term) from json_path
    - Creates a DB named 'courses_{year}_{term}.db'
    - Initializes the FTS table (with prefix) if needed
    - Inserts all courses specific to that file
    - Populates course_data_map[(year, term)] and course_dept_map[(year, term)]
    """
    year, term = parse_year_term_from_filename(json_path)
    db_name = f'courses_{year}_{term}.db'
    
    with open(json_path) as f:
        all_courses = json.load(f)

    conn = get_connection(db_name)
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")

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

    row_count = cur.execute('SELECT count(*) FROM courses_fts;').fetchone()[0]
    if row_count == 0:
        for course in all_courses:
            code = course['code']
            codeWithSpace = course.get('codeWithSpace', '')
            name = course.get('name', '')
            description = course.get('description', '')
            prerequisites = course.get('prerequisites', '')

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

    # Build the code->course map and code->deptName map
    local_course_map = {}
    local_dept_map = {}
    for course in all_courses:
        local_course_map[course['code']] = course
        sections = course.get('sections', [])
        dept_name = sections[0].get("deptName", "") if sections else ""
        local_dept_map[course['code']] = dept_name

    course_data_map[(year, term)] = local_course_map
    course_dept_map[(year, term)] = local_dept_map

# Initialize a DB for each final JSON on startup
for jpath in json_files:
    init_db_for_file(jpath)

# -------------------------------------------------------------------
# 3. Modify the /api/get_courses route to accept year and term,
#    then query the correct DB.
# -------------------------------------------------------------------
@app.route("/api/get_courses", methods=['POST'])
def get_courses():
    """
    Receives a JSON body with:
      - searchTerm: the query string
      - itemsPerPage: number of items per page
      - startFrom: offset for pagination
      - year:  '25'
      - term:  'fall', 'summer', 'spring', etc.
    Returns a JSON list of matched courses, from the correct DB.
    """
    data = request.json
    searchTerm = data.get('searchTerm', '').strip()
    itemsPerPage = data.get('itemsPerPage', 20)
    startFrom = data.get('startFrom', 0)
    year = data.get('year')
    term = data.get('term')

    # Validate year/term
    if not year or not term:
        return jsonify({"error": "Missing 'year' or 'term' in request body"}), 400

    db_name = f'courses_{year}_{term}.db'
    # Look up the relevant code->course dictionary
    codes_dict = course_data_map.get((year, term), {})

    if not searchTerm:
        return jsonify([])

    terms = searchTerm.split()
    prefix_terms = [term + '*' for term in terms]
    fts_query = ' '.join(prefix_terms)

    conn = get_connection(db_name)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

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
        course_obj = codes_dict.get(code, {})
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
    year = data.get('year')
    term = data.get('term')

    formatted_taken_courses = [
        format_course_code(course.rstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ '))
        for course in taken_courses
    ]

    # Add each taken course as a node
    for course in formatted_taken_courses:
        G.add_node(course)

    initiateList(G, selected_major, year, term)

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

def initiateList(G, selected_major, year, term):
    if not selected_major:
        return

    # Access the correct course_dept_map and course_data_map for the given year and term
    dept_map = course_dept_map.get((year, term), {})
    course_map = course_data_map.get((year, term), {})

    # Filter courses by department name
    relevant_courses = {
        code for code, dept in dept_map.items()
        if selected_major in dept
    }

    for course_code in relevant_courses:
        course = course_map.get(course_code, {})
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