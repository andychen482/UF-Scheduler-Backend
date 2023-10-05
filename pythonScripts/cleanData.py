import json
import os
from datetime import datetime

def alphabeticalNoDuplicates(directory):
    # Helper function to convert time to 24-hour format
    def convert_to_24_hour(time_str):
        return datetime.strptime(time_str, '%I:%M %p').strftime('%H:%M')

    # Read the JSON file
    with open(directory) as file:
        data = json.load(file)

    # Initialize the array to store all courses
    all_courses = []

    # Iterate over the data and extract courses
    for item in data:
        courses = item.get('COURSES', [])
        all_courses.extend(courses)

    # Remove duplicate courses
    unique_courses_set = set()
    for course in all_courses:
        unique_courses_set.add(json.dumps(course, sort_keys=True))

    # Convert the set back to a list of dictionaries
    unique_courses = [json.loads(course) for course in unique_courses_set]

    # Sort the courses
    unique_courses.sort(key=lambda x: (x['code'], x['name'], x['termInd']))

    # Print the number of unique courses
    print(f"Number of unique courses: {len(unique_courses)}")

    # Extract the file name without the extension
    file_name = os.path.splitext(os.path.basename(directory))[0]

    # Define the output file name
    output_folder = '../courses/'
    output_file_name = os.path.join(output_folder, file_name + '_clean.json')

    # Convert meetTimeBegin and meetTimeEnd to 24-hour format
    for course in unique_courses:
        for section in course['sections']:
            for meetTime in section['meetTimes']:
                meetTime['meetTimeBegin'] = convert_to_24_hour(meetTime['meetTimeBegin'])
                meetTime['meetTimeEnd'] = convert_to_24_hour(meetTime['meetTimeEnd'])

    # Load professor data
    with open('RateMyProfessorData.json', 'r') as f:
        professors = json.load(f)

    # Add avgRating and avgDifficulty to instructors
    for course in unique_courses:
        for section in course['sections']:
            for instructor in section['instructors']:
                instructor_name = instructor['name']
                if instructor_name in professors:
                    instructor['avgRating'] = professors[instructor_name]['avgRating']
                    instructor['avgDifficulty'] = professors[instructor_name]['avgDifficulty']

    # Write data to file
    with open(output_file_name, 'w') as file:
        json.dump(unique_courses, file, indent=4)
