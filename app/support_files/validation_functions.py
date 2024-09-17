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
