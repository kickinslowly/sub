from pypdf import PdfReader, PdfWriter
from datetime import datetime
import os
from helpers import calculate_hours_from_time_range


# Define the PDF field mapping with lambda functions
PDF_FIELD_MAP = {
    "EMPLOYEE_NAME": lambda teacher, req, sub: teacher.name,
    "DATE_ABSENT": lambda t, r, s: r.date.strftime("%m/%d/%Y"),
    
    "TOTAL_DAYS_ABSENT": lambda t, r, s: "1" if abs(calculate_hours_from_time_range(r.time) - 7) <= 0.5 else "",
    "TOTAL_HOURS_ABSENT": lambda t, r, s: "" if abs(calculate_hours_from_time_range(r.time) - 7) <= 0.5 else f"{round(calculate_hours_from_time_range(r.time), 2)}",

    # Campus checkboxes - using schools relationship instead of legacy campus field
    "PAHS": lambda t, r, s: "Yes" if any(school.code.strip().upper() == "PAHS" for school in t.schools) else "Off",
    "SCHS": lambda t, r, s: "Yes" if any(school.code.strip().upper() in ["SCHS", "PCC"] for school in t.schools) else "Off",  # Map PCC to SCHS
    "AUES": lambda t, r, s: "Yes" if any(school.code.strip().upper() == "AUES" for school in t.schools) else "Off",
    "MAINTENANCE": lambda t, r, s: "Yes" if any(school.code.strip().upper() == "MAINTENANCE" for school in t.schools) else "Off",
    "CAFETERIA": lambda t, r, s: "Yes" if any(school.code.strip().upper() == "CAFETERIA" for school in t.schools) else "Off",
    "TRANSPORTATION": lambda t, r, s: "Yes" if any(school.code.strip().upper() == "TRANSPORTATION" for school in t.schools) else "Off",
    "DO": lambda t, r, s: "Yes" if any(school.code.strip().upper() == "DO" for school in t.schools) else "Off",

    # Reason checkboxes (skip if reason is "School Business")
    "REASON_ILLNESS": lambda t, r, s: "Yes" if r.reason == "Sickness" else "Off",
    "REASON_MEDICAL": lambda t, r, s: "Yes" if r.reason == "Medical" else "Off",
    "REASON_PERSONAL": lambda t, r, s: "Yes" if r.reason == "Personal" else "Off",

    # Skip marking reason if school business
    "REASON_OTHER": lambda t, r, s: "Off" if r.reason == "School Business" else ("Yes" if r.reason not in ["Sickness", "Medical", "Personal"] else "Off"),

    "ABSENT_1": lambda t, r, s: r.date.strftime("%m/%d/%Y"),
    "SUB_NAME1": lambda t, r, s: s.name,

    "ABSENT_1_HOURS_DAYS": lambda t, r, s: (
        "1 day" if abs(calculate_hours_from_time_range(r.time) - 7) <= 0.5 
        else f"{round(calculate_hours_from_time_range(r.time), 2)} hours"
    ),

    "DAYS_TOTAL": lambda t, r, s: "Yes" if abs(calculate_hours_from_time_range(r.time) - 7) <= 0.5 else "Off",
    "HOURS_TOTAL": lambda t, r, s: "Yes" if abs(calculate_hours_from_time_range(r.time) - 7) > 0.5 else "Off",
}

def fill_absence_form(teacher_name: str, request_date: str, data: dict, template_path: str = "static/absence_report.pdf"):
    """
    Fills out the absence report form and saves it in the static folder.

    Parameters:
    - teacher_name (str): Full name of the teacher (e.g., "John Smith")
    - request_date (str): Date string in 'YYYY-MM-DD' format (e.g., "2025-11-15")
    - data (dict): Dictionary mapping PDF form field names to values
    - template_path (str): Path to the base fillable PDF template
    
    Returns:
    - str: Path to the generated PDF file
    """

    # Format the output filename
    safe_teacher_name = teacher_name.replace(" ", "_")
    output_filename = f"filled_absence_report_{safe_teacher_name}_{request_date}.pdf"
    output_path = os.path.join("static", output_filename)

    # Load template and clone
    reader = PdfReader(template_path)
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)

    # Fill form fields on page 0
    writer.update_page_form_field_values(writer.pages[0], data)

    # Write output
    with open(output_path, "wb") as f:
        writer.write(f)

    return output_path  # Return path for further use

def generate_absence_form_data(sub_request, teacher, substitute):
    """
    Generates the data dictionary for filling the absence form based on the substitute request.
    
    Parameters:
    - sub_request: The SubstituteRequest object
    - teacher: The User object for the teacher
    - substitute: The User object for the substitute
    
    Returns:
    - dict: Dictionary mapping PDF form field names to values
    """
    # Use the PDF_FIELD_MAP to generate the form data
    form_data = {}
    
    for field, value_func in PDF_FIELD_MAP.items():
        form_data[field] = value_func(teacher, sub_request, substitute)
    
    return form_data