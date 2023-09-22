import json
from datetime import datetime
import os


def cleanTime(directory):
    # Load the JSON data
    with open(directory, 'r') as file:
        data = json.load(file)

    # Function to convert 12-hour time format to 24-hour time format
    def convert_to_24_hour(time_str):
        return datetime.strptime(time_str, '%I:%M %p').strftime('%H:%M')

    # Iterate through each course
    for course in data:
        # Iterate through each section
        for section in course['sections']:
            # Iterate through each meetTime
            for meetTime in section['meetTimes']:
                # Convert meetTimeBegin and meetTimeEnd to 24-hour format
                meetTime['meetTimeBegin'] = convert_to_24_hour(meetTime['meetTimeBegin'])
                meetTime['meetTimeEnd'] = convert_to_24_hour(meetTime['meetTimeEnd'])

    # Save the updated JSON data
    # Write the unique courses data into a file with the same name but with '_clean' tag added
    file_name = os.path.splitext(os.path.basename(directory))[0]
    output_folder = '../courses/'
    output_file_name = os.path.join(output_folder, file_name + '_clean.json')
    with open(output_file_name, 'w') as file:
        json.dump(data, file, indent=4)

    print("Time conversion completed!")
