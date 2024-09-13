from typing_extensions import Annotated, Optional
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage
from support_files.graph_connection import neo4j_connection
from support_files.validation_functions import validate_email_address,validate_civil_id, validate_phone_number, _validate_customer_info
from support_files.cypher_queries import is_phone_number_exist_query, is_civil_id_exist_query, is_emaild_exist_query
from pyjarowinkler import distance
graph = neo4j_connection()

@tool
def customer_existence_verification(name: str = None, email: str = None, phone: str = None, civil_id: str = None):
    """
    Verify the existence of the Customer in our Database before lead creation.
    
    Parameters:
    - name: Customer's name (optional).
    - email: Customer's email (optional).
    - phone: Customer's phone (optional).
    - civil_id: Customer's civil ID (optional).
    
    Returns:
    - Clear and actionable messages for the lead agent to understand the verification results.
"""
    def get_value(attributes):
        return None if attributes is None or attributes.strip() == "" else attributes

    name = get_value(name)
    email = get_value(email)
    phone = get_value(phone)
    civil_id = get_value(civil_id)
    def validation():
        phone_validation = True
        civil_validation = True
        email_validation = True

        if phone:
            phone_validation = validate_phone_number(phone)
            if phone_validation is not True:
                return phone_validation
        
        if civil_id:
            civil_validation = validate_civil_id(civil_id)
            if civil_validation is not True:
                return civil_validation
        
        if email:
            email_validation = validate_email_address(email)
            if email_validation is not True:
                return email_validation

        # If all validations pass, return True
        return all([phone_validation, civil_validation, email_validation])

    validated = validation()

    if validated == True:

        query = graph.query("""MATCH (c:Lead) RETURN c.name AS customer_name""")
        names_list = [name for i in query for name in [i['customer_name']]]

        def split_names(names):
            return [name.split(' ', 1) if ' ' in name else name for name in names]

        names_list = split_names(names_list)
        def similar_names(user_name, names_list, threshold=0.86):
            similar_names = []
            for name in names_list:
                if isinstance(name, str):
                    similarity = distance.get_jaro_distance(user_name, name)
                    if similarity >= threshold:
                        similar_names.append((name, similarity))
                else:
                    for i in name:
                        similarity = distance.get_jaro_distance(user_name, i)
                        if similarity >= threshold:
                            similar_names.append((' '.join(name), similarity))
            return similar_names

        if name and all(x is None for x in (phone, civil_id, email)):

            name_result = similar_names(name, names_list, threshold=0.86)
            print(name_result)
            if name_result:
                return f"The provided Name is associated with the following customer(s): {[i[0] for i in name_result]}. Would you like to proceed with one of these customers, or would you prefer to create a new lead?"        
            else:
                return f"No matching results were found for the name '{name}'. Please review or confirm the provided details. Would you like to create a new lead instead?"

        else:
            query = """
            MATCH (l:Lead)
            WHERE toLower(l.name) = toLower($name)
            """
            conditions = []
            if phone:
                conditions.append("l.phone_number = $phone")
            if civil_id:
                conditions.append("l.civil_id = $civil_id")
            if email:
                conditions.append("l.email = $email")
            
            if conditions:
                query += " AND " + " AND ".join(conditions)

            query += """
            RETURN l.name AS lead_name, l.phone_number AS phone_number, l.civil_id AS civil_id, l.email AS email, l.id AS lead_id
            """        
            verified_result = graph.query(query, {
                'name': name,
                'phone': phone,
                'civil_id': civil_id,
                'email': email
            })

            if verified_result:
                return f"A customer named '{name}' already exists in our system with matching details (Phone: {verified_result[0]['phone_number']}, Email: {verified_result[0]['email']}, Civil ID: {verified_result[0]['civil_id']}). Would you like to proceed with this customer, or create a new lead?"
            
            else:        
                cypher_queries = []
                semi_verified_result = []

                if phone:
                    phone_query = """
                    MATCH (c:Lead)
                    WHERE c.phone_number = $phone 
                    RETURN c.name AS customer_name, c.phone_number AS phone_number, c.email AS email, c.civil_id AS civil_id
                    """
                    cypher_queries.append(("phone number", phone_query))

                if civil_id:
                    civil_id_query = """
                    MATCH (c:Lead) 
                    WHERE c.civil_id = $civil_id 
                    RETURN c.name AS customer_name, c.phone_number AS phone_number, c.email AS email, c.civil_id AS civil_id
                    """
                    cypher_queries.append(("civil ID", civil_id_query))

                if email:
                    email_query = """
                    MATCH (c:Lead) 
                    WHERE c.email = $email 
                    RETURN c.name AS customer_name, c.phone_number AS phone_number, c.email AS email, c.civil_id AS civil_id
                    """
                    cypher_queries.append(("email", email_query))

                for query_type, query in cypher_queries:
                    db_result = graph.query(query, {
                        'name': name,
                        'phone': phone,
                        'civil_id': civil_id,
                        'email': email
                    })

                    if db_result:
                        return f"I have identified that the {query_type} you provided is associated with {db_result[0]['customer_name']}. Could you please confirm or provide the correct {query_type} for {name}?"

                    else:
                        return f"I was unable to locate the {query_type} ({phone if query_type == 'phone number' else civil_id if query_type == 'civil ID' else email}) in our system. Would you like to proceed with creating a new lead?"
    else:return validated

@tool
def customer_lead_creation(
    customer_name: Annotated[str, "Customer name in lower case"],
    customer_phone: Annotated[str, "Customer phone number in 10 digits"],
    customer_civil: Annotated[str, "Customer civil status"],
    customer_email: Annotated[str, "Customer email address"],
) -> dict:
    """
    Creates a new customer lead by validating the provided customer information and checking for existing associations.
    
    Parameters:
        customer_name (str): The customer's name in lower case. (mandatory)
        customer_phone (str): The customer's phone number in digits.(mandatory)
        customer_civil (str): The customer's civil status.(mandatory)
        customer_email (str): The customer's email address.(mandatory)

    Returns:
        dict: A dictionary containing the result of the lead creation process, including any error messages or a success status.
    """
    # Validate customer information
    validation_result = _validate_customer_info(
        customer_phone=customer_phone,
        customer_civil=customer_civil,
        email=customer_email
    )
    
    if validation_result != "valid":
        def check_existence(query: str, params: dict, identifier: str) -> str:
            query_result = graph.query(query=query, params=params)
            if query_result:
                return f"This {identifier} already associated with {query_result[0]['corresponding_customer']}. Kindly provide your {identifier}"
            return None

        # Check for existing phone number
        phone_message = check_existence(is_phone_number_exist_query, {"phone_number": customer_phone}, customer_phone)
        if phone_message:
            return phone_message

        # Check for existing civil ID
        civil_message = check_existence(is_civil_id_exist_query, {"civil_id": customer_civil}, customer_civil)
        if civil_message:
            return civil_message

        # Check for existing email
        email_message = check_existence(is_emaild_exist_query, {"customer_email": customer_email}, customer_email)
        if email_message:
            return email_message

        return {"status": "Lead creation successful."}