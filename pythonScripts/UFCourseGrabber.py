import sys
import requests
import json
import os
from datetime import date
import threading
import logging
import glob
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Get the current script's directory
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)

# Check if 'courses' directory exists and create it if it doesn't
courses_dir = os.path.join(parent_dir, 'courses')
if not os.path.exists(courses_dir):
    os.makedirs(courses_dir)

class Counter:
    def __init__(self):
        self.value = 0
        self._lock = threading.Lock()

    def increment(self):
        with self._lock:
            self.value += 1

counter = Counter()

def scrape_page(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raises stored HTTPError, if one occurred.
    except requests.HTTPError as http_err:
        logging.error(f'HTTP error occurred: {http_err}')
        os._exit(1)
        return []
    except Exception as err:
        logging.error(f'Other error occurred: {err}')
        os._exit(1)
        return []

    try:
        data = response.json()
    except ValueError:  # includes simplejson.decoder.JSONDecodeError
        logging.error('Decoding JSON has failed')
        os._exit(1)
        return []

    if isinstance(data, list):  # Changed this to list as you mentioned the type of data is list
        return data
    else:
        logging.info("Data is not a list.")
        os._exit(1)
        return []  # Return an empty list if data is not a list

def save_text_to_json_file(text, filename):
    filename = os.path.join(courses_dir, filename)  # Add 'courses' directory to the filename
    
    # Check if file exists
    try:
        if os.path.exists(filename):
            # If it exists, open it and load the existing data
            with open(filename, 'r') as f:
                existing_data = json.load(f)
        else:
            # If it doesn't exist, create an empty list to hold the data
            existing_data = []
    except json.JSONDecodeError:
        logging.error('Failed to decode JSON from file')
        os._exit(1)
        existing_data = []

    # Remove unwanted keys from the text
    keys_to_remove = ['LASTCONTROLNUMBER', 'TOTALROWS', 'RETRIEVEDROWS']
    for item in text:
        for key in keys_to_remove:
            item.pop(key, None)

    # Add the new data to the existing data
    existing_data.extend(text)

    # Write the updated data to the file
    try:
        with open(filename, 'w') as f:
            json.dump(existing_data, f, indent=4)
    except IOError:
        logging.error('Failed to write to file')
        os._exit(1)

def thread_handler(thread_id, controlNum_start, url, term, year, increment=16):
    filename = date.today().strftime("%b-%d-%Y") + f'_{year}_{term}_thread{thread_id}.json'
    filename = os.path.join(courses_dir, filename)  # Add 'courses' directory to the filename

    controlNum = controlNum_start
    filename = date.today().strftime("%b-%d-%Y") + f'_{year}_{term}_thread{thread_id}.json'
    while True:  # Infinite loop, we'll break it when no more data
        full_url = url + str(controlNum)
        logging.info(f'Thread-{thread_id}: {full_url}')
        data = scrape_page(full_url)
        if not data or data[0]['RETRIEVEDROWS'] == 0:  # If data is empty or RETRIEVEDROWS is 0, we assume there's no more data and break the loop
            break

        save_text_to_json_file(data, filename)
        controlNum += 50 * increment
        counter.increment()

def merge_json_files(term, year):
    all_data = []
    files = glob.glob(os.path.join(courses_dir, date.today().strftime("%b-%d-%Y") + f'_{year}_{term}_thread*.json'))

    for file in files:
        with open(file, 'r') as f:
            data = json.load(f)
            all_data.extend(data)

    final_filename = 'UF_' + date.today().strftime("%b-%d-%Y") + f'_{year}_{term}.json'
    final_filename = os.path.join(courses_dir, final_filename)
    with open(final_filename, 'w') as f:
        json.dump(all_data, f, indent=4)

    # Delete the individual thread files
    for file in files:
        try:
            os.remove(file)
        except OSError as e:
            logging.error(f'Error while deleting file {file}. Error message: {e.strerror}')
            os._exit(1)

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
    output_folder = 'courses/'
    output_file_name = os.path.join(output_folder, file_name + '_clean.json')

    # Convert meetTimeBegin and meetTimeEnd to 24-hour format
    for course in unique_courses:
        course['codeWithSpace'] = course['code'][:3] + ' ' + course['code'][3:]
        for section in course['sections']:
            del section['EEP']
            del section['LMS']
            del section['acadCareer']
            del section['addEligible']
            del section['dNote']
            section['courseCode'] = course['code']
            for meetTime in section['meetTimes']:
                meetTime['meetTimeBegin'] = convert_to_24_hour(meetTime['meetTimeBegin'])
                meetTime['meetTimeEnd'] = convert_to_24_hour(meetTime['meetTimeEnd'])

    # # Load professor data
    # with open('RateMyProfessorData.json', 'r') as f:
    #     professors = json.load(f)

    # # Add avgRating and avgDifficulty to instructors
    # for course in unique_courses:
    #     for section in course['sections']:
    #         for instructor in section['instructors']:
    #             instructor_name = instructor['name']
    #             if instructor_name in professors:
    #                 instructor['avgRating'] = professors[instructor_name]['avgRating']
    #                 instructor['avgDifficulty'] = professors[instructor_name]['avgDifficulty']

    # Write data to file
    with open(output_file_name, 'w') as file:
        json.dump(unique_courses, file, indent=4)


if __name__ == '__main__':
    # Check if correct number of arguments are given
    if len(sys.argv) < 3:
        print("Usage: script.py <term> <year> [<term> <year> ...]")
        sys.exit(1)

    terms = sys.argv[1:]
    for i in range(0, len(terms), 2):
        term = terms[i].lower()
        year = terms[i + 1]

        if term not in ['spring', 'summer', 'fall']:
            print("Term should be either 'spring', 'summer', or 'fall'")
            sys.exit(1)

        try:
            year = int(year)
            if year < 0 or year > 99:
                raise ValueError
        except ValueError:
            print("Year should be a two-digit number between 00 and 99")
            sys.exit(1)

        # Delete existing JSON files for the current term and year
        current_files = glob.glob(os.path.join(courses_dir, f'*_{year}_{term}.json'))
        for file in current_files:
            try:
                os.remove(file)
            except OSError as e:
                logging.error(f'Error while deleting file {file}. Error message: {e.strerror}')
                sys.exit(1)

        term_dict = {'spring': '1', 'summer': '5', 'fall': '8'}
        term_num = str(2) + str(year) + term_dict[term]

        url = f'https://one.ufl.edu/apix/soc/schedule/?category=RES&term={term_num}&last-control-number='
        threads = []
        for i in range(16):  # Create 16 threads
            t = threading.Thread(target=thread_handler, args=(i, 50 * i, url, term, year))
            t.start()
            threads.append(t)

        for t in threads:  # Wait for all threads to finish
            t.join()

        print(f'Total API calls for {term} {year}: {counter.value}')

        # Merge all thread files into one final file
        merge_json_files(term, year)

        # Get a list of all JSON files in the 'courses' directory for the current term and year
        json_files = glob.glob(os.path.join(courses_dir, f'*_{year}_{term}.json'))

        # Iterate over each JSON file
        for file in json_files:
            if not file.endswith("_clean.json"):  # Check if the file does not already have "_clean.json" at the end
                # Call alphabeticalNoDuplicates() from cleanData module with the file as a parameter
                alphabeticalNoDuplicates(file)

                # Delete the original file
                try:
                    os.remove(file)
                    print(f"Deleted file: {file}\n\n\n\n\n")
                except OSError as e:
                    logging.error(f'Error while deleting file {file}. Error message: {e.strerror}')
                    sys.exit(1)
        
        # Reset the counter value for the next iteration
        counter.value = 0