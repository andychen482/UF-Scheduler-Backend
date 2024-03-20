import requests
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import glob
import os

url = 'https://www.ratemyprofessors.com/graphql'

professor = set()

course_file = glob.glob("../courses/*.json")[0]

with open(course_file) as file:
    data = json.load(file)

for course in data:
    for section in course['sections']:
        for instructor in section['instructors']:
            if instructor["name"] != "":
                professor.add(instructor["name"])

# Dictionary to store professor data
professor_data = {}
lock = threading.Lock()


headers = {
    'Accept': '*/*',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'en-US,en;q=0.9,es;q=0.8',
    'Authorization': 'Basic dGVzdDp0ZXN0',
    'Connection': 'keep-alive',
    'Content-Type': 'application/json',
    'Cookie': 'ccpa-notice-viewed-02=true; cid=AuVRpwXwX2-20231004',
    'DNT': '1',
    'Host': 'www.ratemyprofessors.com',
    'Origin': 'https://www.ratemyprofessors.com',
    'Referer': 'https://www.ratemyprofessors.com/search/professors/1100?q=*',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
    'sec-ch-ua': '"Google Chrome";v="117", "Not;A=Brand";v="8", "Chromium";v="117"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': 'Windows'
}

def merge_course_and_professor_data(course_file, professor_data_file):
    with open(course_file, 'r') as f:
        courses = json.load(f)

    with open(professor_data_file, 'r') as f:
        professors = json.load(f)

    for course in courses:
        for section in course['sections']:
            for instructor in section['instructors']:
                instructor_name = instructor["name"]
                if instructor_name in professors:
                    instructor.update(professors[instructor_name])

    # Save merged data to a new file
    merged_file_name = course_file.replace('_clean', '_final')
    with open(merged_file_name, 'w') as f:
        json.dump(courses, f, indent=4)
    
    os.remove(course_file)


def fetch_professor_data(prof):
  print(f"Fetching data for professor {prof}...")
  payload = {
      "query": """
          query TeacherSearchResultsPageQuery(
            $query: TeacherSearchQuery!
            $schoolID: ID
          ) {
            search: newSearch {
              ...TeacherSearchPagination_search_1ZLmLD
            }
            school: node(id: $schoolID) {
              __typename
              ... on School {
                name
              }
              id
            }
          }

          fragment TeacherSearchPagination_search_1ZLmLD on newSearch {
            teachers(query: $query, first: 8, after: "") {
              didFallback
              edges {
                cursor
                node {
                  ...TeacherCard_teacher
                  id
                  __typename
                }
              }
              pageInfo {
                hasNextPage
                endCursor
              }
              resultCount
              filters {
                field
                options {
                  value
                  id
                }
              }
            }
          }

          fragment TeacherCard_teacher on Teacher {
            id
            legacyId
            avgRating
            numRatings
            ...CardFeedback_teacher
            ...CardSchool_teacher
            ...CardName_teacher
            ...TeacherBookmark_teacher
          }

          fragment CardFeedback_teacher on Teacher {
            wouldTakeAgainPercent
            avgDifficulty
          }

          fragment CardSchool_teacher on Teacher {
            department
            school {
              name
              id
            }
          }

          fragment CardName_teacher on Teacher {
              firstName
              lastName
          }

          fragment TeacherBookmark_teacher on Teacher {
              id
              isSaved
          }
          """,  # Continue from where you left off
        "variables": {
            "count": 8,
            "cursor": "YXJyYXljb25uZWN0aW9uOjc=",
            "query": {
                "text": prof,
                "schoolID": "U2Nob29sLTExMDA=",
                "fallback": True,
                "departmentID": None
            }
        }
    }

  response = requests.post(url, json=payload, headers=headers)
  local_data = {}

  if response.status_code == 200:
      try:
          response_data = response.json()
          teacher_edges = response_data.get("data", {}).get("search", {}).get("teachers", {}).get("edges", [])
          for edge in teacher_edges:
              node = edge["node"]
              if node["numRatings"] > 0:
                  local_data[prof] = {
                      "avgRating": node["avgRating"],
                      "avgDifficulty": node["avgDifficulty"]
                  }
                  break  # Break once we found a valid teacher node
      except json.JSONDecodeError:
          print(f"Failed to decode JSON for professor {prof}.")


  # Using a lock to prevent simultaneous writes to the shared dictionary
  with lock:
      professor_data.update(local_data)

with ThreadPoolExecutor(max_workers=16) as executor:
    futures = [executor.submit(fetch_professor_data, prof) for prof in professor]
    for future in as_completed(futures):
        # Just to handle any exceptions that might have been raised inside our function
        future.result()

# Saving professor data to RateMyProfessorData.json
with open("RateMyProfessorData.json", "w") as file:
    json.dump(professor_data, file, indent=4)
    print("Professor data saved to RateMyProfessorData.json")

merge_course_and_professor_data(course_file, "RateMyProfessorData.json")