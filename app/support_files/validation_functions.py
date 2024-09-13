import re

def validate_phone(customer_phone: str) -> str:
    """
    Validates a phone number input.

    Parameters:
    input_widget (str): The phone number as a string.

    Returns:
    str: "valid" if the phone number is exactly 10 digits long and contains only digits,
         "invalid" if the phone number contains any non-digit characters,
         "Phone number should be 10 digits" if the phone number is not exactly 10 digits long.
    """
    if len(customer_phone) != 10:
        return "Phone number should be 10 digits"
    return "valid" if customer_phone.isdigit() else "invalid"

def validate_civil(customer_civil: str) -> str:
    """
    Validates a civil identification number.

    Parameters:
    input_widget (str): The civil identification number as a string.

    Returns:
    str: "valid" if the civil identification number is exactly 12 digits long and contains only digits,
         "invalid" if the civil identification number contains any non-digit characters,
         "Civil ID should be 12 digits" if the civil identification number is not exactly 12 digits long.
    """
    if len(customer_civil) != 12:
        return "Civil ID should be 12 digits"
    return "valid" if customer_civil.isdigit() else "invalid"

def validate_email(email: str) -> str:
    """
    Validates an email address by replacing the domain with 'gmail.com' and then checking if the email is valid.

    Parameters:
    email (str): The email address to validate.

    Returns:
    str: "valid" if the email address with the 'gmail.com' domain is valid,
         "invalid email" if the email format is incorrect.
    """
    local_part, domain = email.split("@")
    email = f"{local_part}@gmail.com"
    
    pattern = r"^[a-z0-9]+[\._]?[a-z0-9]+[@]gmail[.]com$"
    
    if re.match(pattern, email):
        print(email)
        return "valid"
    else:
        return "invalid email"
    
import re

def _validate_customer_info(
    customer_phone: str,
    customer_civil: str,
    email: str
) -> str:
    """
    Validates customer information, including phone number, civil ID, and email address.

    Parameters:
    customer_phone (str): The phone number as a string.
    customer_civil (str): The civil identification number as a string.
    email (str): The email address to validate.

    Returns:
    str: "valid" if all validations pass,
         "Phone number should be 10 digits" if the phone number is not exactly 10 digits long,
         "Phone number should only contain digits" if the phone number contains any non-digit characters,
         "Civil ID should be 12 digits" if the civil identification number is not exactly 12 digits long,
         "Civil ID should only contain digits" if the civil identification number contains any non-digit characters,
         "Invalid email format" if the email format is incorrect.
    """
    # Validate phone number
    if len(customer_phone) != 10:
        return "Phone number should be 10 digits"
    if not customer_phone.isdigit():
        return "Phone number should only contain digits"

    # Validate civil ID
    if len(customer_civil) != 12:
        return "Civil ID should be 12 digits"
    if not customer_civil.isdigit():
        return "Civil ID should only contain digits"

    # Validate email
    local_part, domain = email.split("@")
    email = f"{local_part}@gmail.com"
    pattern = r"^[a-z0-9]+[\._]?[a-z0-9]+[@]gmail[.]com$"
    if not re.match(pattern, email):
        return "Invalid email format"

    return "valid"


import phonenumbers
from email_validator import validate_email, EmailNotValidError
from phonenumbers import NumberParseException, is_valid_number
import re

def validate_email_address(email):
    """
    Validate the email address format and provide feedback to the lead agent.
    """
    try:
        valid = validate_email(email)
        email = valid.email
        return True
    except EmailNotValidError as e:
        return f"The email address '{email}' is invalid. Please verify and provide a correct email address format."

def validate_phone_number(number: str):
    """
    Validate the phone number format including the country code and provide feedback to the lead agent.
    """
    if not number.startswith('+'):
        return "The phone number must include the country code (e.g., +1 for the US). Please provide the correct format."

    if not number[1:].replace("-", "").replace(" ", "").isdigit():
        return "The phone number contains invalid characters. Ensure that it only contains digits, spaces, or hyphens after the country code."

    try:
        phone_number = phonenumbers.parse(number)
        if is_valid_number(phone_number):
            return True
        else:
            return f"The phone number '{number}' is not valid. Please double-check the number and try again."
    except NumberParseException:
        return f"An error occurred while validating the phone number '{number}'. Please verify that it is in the correct international format."

def validate_civil_id(civil_id):
    """
    Validate the Civil ID format and provide feedback to the lead agent.
    """
    civil_id_regex = r'^\d{12}$'

    if re.fullmatch(civil_id_regex, civil_id):
        return True
    else:
        return f"The Civil ID '{civil_id}' is invalid. A valid Civil ID should contain exactly 12 digits with no other characters."
