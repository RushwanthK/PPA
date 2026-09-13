from datetime import datetime

def parse_date(date_str):
    return datetime.strptime(date_str, "%Y-%m-%d").date()

def calculate_age(dob):
    today = datetime.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))