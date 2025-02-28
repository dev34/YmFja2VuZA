import requests
from bs4 import BeautifulSoup
import cssutils
import re
import logging
import json

cssutils.log.setLevel(logging.CRITICAL)

class ScheduleProcessor:
    def __init__(self, room_names, room_locations, room_times, lab_names, lab_locations, lab_times,department):
        self.room_names = room_names
        self.room_locations = room_locations
        self.room_times = room_times
        self.lab_names = lab_names
        self.lab_locations = lab_locations
        self.lab_times = lab_times
        self.department = department
        self.final_schedule = {}

    def extract_section(self, name):
        """Extract the section (e.g., A, B) from the name."""
        if self.department == "BS CY":
            match = re.search(r'\(CY-([A-Z0-9]+)', name)
        elif self.department == "BS CS":
            match = re.search(r'\(CS-([A-Z0-9]+)', name)
        elif self.department == "BS SE":
            match = re.search(r'\(SE-([A-Z0-9]+)', name)
        elif self.department == "BS AI":
            match = re.search(r'\(AI-([A-Z0-9]+)', name)
        elif self.department == "BS DS":
            match = re.search(r'\(DS-([A-Z0-9]+)', name)
        if match:
            if (len(match.group(1))!=1) and (match.group(1)[0].isdigit() == True):
                return match.group(1)[-1]
            else:
                return match.group(1)[0]
        else:
            return None

    def extract_time(self, name):
        """Extract time from the name if explicitly provided."""
        pattern = r'(?:(?<=\s)|^)(\d{1,2}:\d{2}(?:\s?[-:\s]\s?\d{1,2}:\d{2})?|\d{1,2}:\d{2}:\d{2}(?:\s?[-:\s]\s?\d{1,2}:\d{2})?|\d{1,2}:\d{2}:\d{2}:\d{2})(?=\D|$)'
        match = re.search(pattern, name)
        
        return match.group(0) if match else None

    def split_key(self, key):
        """Split the key into its letter (time) and numeric (location) components."""
        match = re.match(r'([A-Z]+)(\d+)', key)
        if match:
            return match.group(1), match.group(2)
        return None, None

    def process_rooms(self):
        """Process room data and populate the final schedule."""
        for key, name in self.room_names.items():
            section = self.extract_section(name)
            if not section:
                continue

            time_letter, location_number = self.split_key(key)
            time = self.extract_time(name) or self.room_times.get(time_letter, 'N/A')
            loc_pattern = r"[A-Z]-?\d{3}" #to check if location is in the name
            extracted_location = re.search(loc_pattern, name)
            if (extracted_location):
                location = extracted_location.group()
            else:
                location = self.room_locations.get(location_number, 'N/A')
            

            self.final_schedule.setdefault(section, []).append({
                'name': name.split('(')[0].strip(),
                'location': location,
                'time': time
            })

    def process_labs(self):
        """Process lab data and populate the final schedule."""
        for key, name in self.lab_names.items():
            section = self.extract_section(name)
            if not section:
                continue
            time_letter, location_number = self.split_key(key)
            time = self.extract_time(name) or (self.lab_times.get(time_letter, 'N/A') if '==half==' not in name else self.room_times.get(time_letter, 'N/A'))
            name = name.replace('==half==', '').strip()
            location = self.lab_locations.get(location_number, 'N/A')
            self.final_schedule.setdefault(section, []).append({
                'name': name.split('(')[0].strip(),
                'location': location,
                'time': time
            })

    def generate_schedule(self):
        """Generate the final schedule."""
        self.process_rooms()
        self.process_labs()
        return self.final_schedule



def col_number_to_letter(col_number):
    letters = ""
    while col_number > 0:
        col_number, remainder = divmod(col_number - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters

def extract_room_times(rows,isFrday=False):
    room_times = {}
    for row in rows:
        cells = row.find_all("td")
        if len(cells) > 0:  
            first_cell_text = cells[0].get_text(strip=True)
            if first_cell_text == "Room":
                column_index = 0
                skipNextIteration = False
                for cell in cells:
                    cell_text = cell.get_text(strip=True)
                    if skipNextIteration == True:
                        skipNextIteration = False
                        continue
                    if isFrday == True and cell_text == "01:00-02:20":
                        skipNextIteration = True
                        continue
                    cell_width = cell.get("colspan")
                    if cell_width != None:
                        column_index += int(cell_width)
                    else:
                        column_index += 1
                    if cell_text == "" or cell_text == "Room":
                        continue
                    col_letter = col_number_to_letter(column_index)
                    coordinates = f"{col_letter}"
                    room_times[coordinates] = cell_text
    return room_times

def extract_lab_times(rows,isFrday=False):
    lab_times = {}
    for row in rows:
        cells = row.find_all("td")
        if len(cells) > 0:  
            first_cell_text = cells[0].get_text(strip=True)
            if first_cell_text == "Lab":
                column_index = 0
                for cell in cells:
                    cell_text = cell.get_text(strip=True)
                    cell_width = cell.get("colspan")
                    if cell_width != None:
                        column_index += int(cell_width)
                    else:
                        column_index += 1
                    if cell_text == "" or cell_text == "Lab":
                        continue
                    col_letter = col_number_to_letter(column_index)
                    coordinates = f"{col_letter}"
                    lab_times[coordinates] = cell_text
    # if isFriday then adjust lab times, to ignore the prayer break by subtracting 3 col letter from the last time
    if (isFrday == True):
        last_key = list(lab_times.keys())[-1]
        new_key = chr(ord(last_key) - 3)
        lab_times[new_key] = lab_times.pop(last_key)
    return lab_times

def programme_course_name_extractor(department,batch,sheet_style_tags, sheet_rows):
    style_tags = sheet_style_tags
    rows = sheet_rows
    #GPT OPTIMIZATION ##############################################################
    css_parser = cssutils.CSSParser()
    style_tag = style_tags[0]
    css_content = css_parser.parseString(style_tag.string)
    css_styles = {match.group(0): rule.style.getPropertyValue("background-color")
                  for rule in css_content.cssRules if rule.type == rule.STYLE_RULE
                  for match in [re.search(r"\.s\d+", rule.selectorText)] if match}
    #################################################################################
    target_text = f"{department} ({batch})"
    target_color = None
    results = {}
    results_lab = {}
    ############ FINDING COLOR ###########
    colorIsIterate = True
    for row in rows:
        cells = row.find_all("td")
        if colorIsIterate == False:
            break
        for cell in cells:
            cell_text = cell.get_text(strip=True)
             
            if cell_text == target_text:
                cell_class = cell.get("class", [])
                for cls in cell_class:
                    if f".{cls}" in css_styles:
                        target_color = css_styles[f".{cls}"]
                        colorIsIterate = False
                        break
    #####################################
    appendToLabs = False
    if target_color:
        for row_index, row in enumerate(rows, start=1):
            cells = row.find_all("td")
            column_index = 0
            if len(cells) > 0:
                if cells[0].get_text(strip=True) == "Lab":
                    appendToLabs = True
            for cell in cells:
                cell_text = cell.get_text(strip=True)
                if (cell_text == "P  R  A  Y  E  R     B  R  E  A  K"):
                    continue
                pattern = r'\b[A-Z]+-[A-Z]\d+\b'
                matches = re.findall(pattern, cell_text)
                if matches:
                    cell_text = cell_text.split("(")
                    cell_text[0] = cell_text[0] + matches[0][-2:]
                    cell_text = " (".join(cell_text)
                if "Cancelled" in cell_text or "cancelled" in cell_text:
                    cell_text = cell_text.split("(")
                    cell_text[0] = cell_text[0] + "[Cancelled]"
                    cell_text = " (".join(cell_text)
                if "ReSch" in cell_text or "Resch" in cell_text or "resch" in cell_text:
                    cell_text = cell_text.replace("ReSch","").strip()
                    cell_text = cell_text.replace("Resch","").strip()
                    cell_text = cell_text.replace("resch","").strip()
                    cell_text = cell_text.split("(")
                    cell_text[0] = cell_text[0] + "[Rescheduled]"
                    cell_text = " (".join(cell_text)
                cell_width = cell.get("colspan")
                if cell_width != None:
                    column_index += int(cell_width)
                else:
                    column_index += 1
                ##### GET CELL COLOR #####
                cell_class = cell.get("class", [])
                cell_color = None
                for cls in cell_class:
                    if f".{cls}" in css_styles:
                        cell_color = css_styles[f".{cls}"]
                        break
                ##########################
                if cell_color == target_color and cell_text != target_text and cell_text!="":
                    col_letter = col_number_to_letter(column_index)
                    coordinates = f"{col_letter}{row_index}"
                    if appendToLabs == True:
                        if (int(cell_width)==2): #lab is not full
                            results_lab[coordinates] = cell_text+"==half=="
                        else:
                            results_lab[coordinates] = cell_text
                    else:
                        results[coordinates] = cell_text
    return results,results_lab

def extract_room_locations(rows):
    room_numbers = {}
    collecting_rooms = False  

    for row_index, row in enumerate(rows, start=1):  
        cells = row.find_all("td")

        if len(cells) > 0:  
            first_cell_text = cells[0].get_text(strip=True) # assuming always first column
            if first_cell_text == "":
                continue
            if first_cell_text == "Room":
                collecting_rooms = True

            if first_cell_text == "Lab":
                collecting_rooms = False
                break  

            if collecting_rooms and first_cell_text != "Room":
                room_number = first_cell_text
                coordinates = f"{row_index}"

                room_numbers[coordinates] = room_number
    return room_numbers

def extract_lab_locations(rows):
    lab_numbers = {}
    collecting_labs = False  

    for row_index, row in enumerate(rows, start=1):  
        cells = row.find_all("td")

        if len(cells) > 0:  
            first_cell_text = cells[0].get_text(strip=True)
            if first_cell_text == "":
                continue
            if first_cell_text == "Lab":

                collecting_labs = True

            if collecting_labs and first_cell_text != "Lab":
                lab_number = first_cell_text
                coordinates = f"{row_index}"

                lab_numbers[coordinates] = lab_number
    return lab_numbers


most_final = {}

# List of departments and batches
batches = ["2021","2022","2023","2024"]
departments = ["BS CY","BS CS","BS SE","BS AI","BS DS"]
days_of_week = {"Monday":1, "Tuesday":2, "Wednesday":3, "Thursday":4, "Friday":5}

# Initialize the dictionary structure
for day in days_of_week.keys():
    most_final[day] = {}  # Add day key
    for dept in departments:
        most_final[day][dept] = {}  # Add department key
        for batch in batches:
            most_final[day][dept][batch] = {}  # Add batch key



SPREADSHEET_ID = "1LP3rof0_h311OND_lvjUaoPbY1ncO4hwDU-4ctr1KHo"
sheet_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/htmlview"


response = requests.get(sheet_url)
soup = BeautifulSoup(response.text, "html.parser")
style_tags = soup.find_all("style")
sheets = soup.find_all("table")

for day,day_index in days_of_week.items():
    worksheet = sheets[day_index]
    rows = worksheet.find_all("tr")

    if (day == "Friday"):
        room_times = extract_room_times(rows,isFrday=True)
        lab_times = extract_lab_times(rows,isFrday=True)
    else:
        room_times = extract_room_times(rows)
        lab_times = extract_lab_times(rows)
    room_locations = extract_room_locations(rows)
    lab_locations = extract_lab_locations(rows)
    for depart in departments:
        for batch in batches:
            room_names,lab_names = programme_course_name_extractor(depart,batch,style_tags,rows)
            processor = ScheduleProcessor(room_names, room_locations, room_times, lab_names, lab_locations, lab_times, depart)
            formatted_data = processor.generate_schedule()
            most_final[day][depart][batch] = formatted_data

with open("timetable.json", "w") as file:
    file.write(json.dumps(most_final, indent=4))
