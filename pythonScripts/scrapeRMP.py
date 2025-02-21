import requests
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import glob
import os

url = "https://www.ratemyprofessors.com/graphql"

# Collect all .json files in "courses" that aren't _clean or _final
course_files = [
    f for f in glob.glob("courses/*.json")
]

professor = set()

# Build professor set from all relevant files
for cf in course_files:
    with open(cf, "r") as file:
        data = json.load(file)
        for course in data:
            for section in course["sections"]:
                for instructor in section["instructors"]:
                    if instructor["name"]:
                        professor.add(instructor["name"])

# Dictionary to store professor data
professor_data = {}
lock = threading.Lock()


headers = {
    'Accept': 'application/json',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Accept-Language': 'en-US,en;q=0.9,es;q=0.8',
    'Authorization': 'Basic dGVzdDp0ZXN0',
    'Connection': 'keep-alive',
    'Content-Type': 'application/json',
    'Cookie': 'ccpa-notice-viewed-02=true; cid=AuVRpwXwX2-20231004',
    'DNT': '1',
    'Host': 'www.ratemyprofessors.com',
    'Origin': 'https://www.ratemyprofessors.com',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'none',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36'
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
  query = """
  query NewSearchTeachersQuery($query: TeacherSearchQuery!) {
      newSearch {
          teachers(query: $query) {
              didFallback
              edges {
                  cursor
                  node {
                      id
                      legacyId
                      firstName
                      lastName
                      avgRatingRounded
                      numRatings
                      wouldTakeAgainPercentRounded
                      wouldTakeAgainCount
                      teacherRatingTags {
                          id
                          legacyId
                          tagCount
                          tagName
                      }
                      mostUsefulRating {
                          id
                          class
                          isForOnlineClass
                          legacyId
                          comment
                          helpfulRatingRounded
                          ratingTags
                          grade
                          date
                          iWouldTakeAgain
                          qualityRating
                          difficultyRatingRounded
                          teacherNote{
                              id
                              comment
                              createdAt
                              class
                          }
                          thumbsDownTotal
                          thumbsUpTotal
                      }
                      avgDifficultyRounded
                      school {
                          name
                          id
                      }
                      department
                  }
              }
          }
      }
  }
  """
  variables = {"query": {"text": prof, "schoolID": "U2Nob29sLTExMDA="}}
  payload = {
      "query": query,
      "variables": variables
  }

  response = requests.post(url, json=payload, headers=headers)
  local_data = {}

  if response.status_code == 200:
      try:
          response_data = response.json()

          if response_data and "data" in response_data:
              teacher_edges = response_data.get("data", {}).get(
                  "newSearch", {}).get("teachers", {}).get("edges", [])
              for edge in teacher_edges:
                  node = edge["node"]
                  if node["numRatings"] > 0 and (node["firstName"] + " " + node["lastName"]).lower() == prof.lower():
                      local_data[prof] = {
                          "avgRating": node.get("avgRatingRounded"),
                          "avgDifficulty": node.get("avgDifficultyRounded"),
                          "professorID": node.get("legacyId")
                      }
                      break  # Break once we found a valid teacher node
      except json.JSONDecodeError:
          print(f"Failed to decode JSON for professor {prof}.")
      except Exception as e:
          print(f"Error processing data for professor {prof}: {str(e)}")
  else:
      print(f"Failed to fetch data for professor {prof}, status code: {response.status_code}")
      return None

  # Using a lock to prevent simultaneous writes to the shared dictionary
  with lock:
      professor_data.update(local_data)

with ThreadPoolExecutor(max_workers=16) as executor:
    futures = [executor.submit(fetch_professor_data, prof) for prof in professor]
    for future in as_completed(futures):
        # Just to handle any exceptions that might have been raised inside our function
        future.result()

# Saving professor data to RateMyProfessorData.json
with open("pythonScripts/RateMyProfessorData.json", "w") as outfile:
    json.dump(professor_data, outfile, indent=4)
    print("Professor data saved to RateMyProfessorData.json")

# Now merge professor data into each file
for cf in course_files:
    merge_course_and_professor_data(cf, "pythonScripts/RateMyProfessorData.json")