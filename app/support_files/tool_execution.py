from typing_extensions import Annotated, Optional
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage
from support_files.graph_connection import neo4j_connection, test_neo4j_connection
from support_files.validation_functions import validate_email_address,validate_civil_id, validate_phone_number
from support_files.cypher_queries import is_phone_number_exist_query, is_civil_id_exist_query, is_emaild_exist_query
from pyjarowinkler import distance
graph = neo4j_connection()
test_graph = test_neo4j_connection()
from datetime import datetime 

@tool
def customer_existence_verification(name: str = None, email: str = None, phone: str = None, civil_id: str = None):
    """
    Verify the existence of the Customer in the database before lead creation.

    Parameters:
    - name: Customer's name (optional).
    - email: Customer's email (optional).
    - phone: Customer's phone (optional).
    - civil_id: Customer's civil ID (optional).

    Returns:
    - Clear and actionable messages for the lead agent to understand the verification results.
    """

    def get_value(attr):
        """Helper function to clean up attribute values."""
        return None if attr is None or attr.strip() == "" or "unknown" in attr.strip() else attr

    # Clean inputs
    name = get_value(name)
    email = get_value(email)
    phone = get_value(phone)
    civil_id = get_value(civil_id)

    if not name and not email and not phone and not civil_id:
        # Ensure at least one parameter is provided
        return "Error: At least one of name, email, phone, or civil ID is required to verify customer existence."

    def validation():
        """Validate the phone, email, and civil ID if provided."""
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

        return True

    validated = validation()

    if validated == True:
        query = graph.query("""MATCH (c:Lead) RETURN c.name AS customer_name""")
        names_list = [name['customer_name'] for name in query]

        def split_names(names):
            """Split full names into first and last for better matching."""
            return [name.split(' ', 1) if ' ' in name else [name] for name in names]

        names_list = split_names(names_list)

        def find_similar_names(input_name, names_list, threshold=0.86):
            """Find similar names in the database based on Jaro-Winkler similarity."""
            similar_names = []
            for name in names_list:
                full_name = ' '.join(name) if isinstance(name, list) else name
                similarity = distance.get_jaro_distance(input_name, full_name)
                if similarity >= threshold:
                    similar_names.append((full_name, similarity))
            return similar_names

        if name and all(param is None for param in (phone, civil_id, email)):
            # Verify only by name
            name_matches = find_similar_names(name, names_list)
            if name_matches:
                matched_names = ', '.join([i[0] for i in name_matches])
                return (
                    f"The provided name is associated with the following customer(s): {matched_names}. "
                    "Would you like to proceed with one of these customers, or create a new lead?"
                )
            else:
                return (
                    f"No matching results found for the name '{name}'. Please review or confirm the provided details. "
                    "Would you like to create a new lead instead?"
                )

        else:
            # Create query with dynamic conditions based on provided data
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

            # Run the query and check if a customer exists with the provided details
            verified_result = graph.query(query, {
                'name': name,
                'phone': phone,
                'civil_id': civil_id,
                'email': email
            })

            if verified_result:
                customer_data = verified_result[0]
                return (
                    f"A customer named '{customer_data['lead_name']}' already exists in our system "
                    f"with matching details (Phone: {customer_data['phone_number']}, Email: {customer_data['email']}, Civil ID: {customer_data['civil_id']}). "
                    "Would you like to proceed with this customer, or create a new lead?"
                )
            else:
                # Handle semi-verified results by running individual queries for each identifier
                cypher_queries = []
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

                # Run each individual query for partial verification
                for query_type, query in cypher_queries:
                    db_result = graph.query(query, {
                        'name': name,
                        'phone': phone,
                        'civil_id': civil_id,
                        'email': email
                    })

                    if db_result:
                        customer_data = db_result[0]
                        return (
                            f"I have identified that the {query_type} you provided is associated with "
                            f"{customer_data['customer_name']}. Could you please confirm or provide the correct {query_type} "
                            f"for {name}?"
                        )

                return (
                    "No matching records found for the provided details. "
                    "Would you like to proceed with creating a new lead?"
                )
    else:
        # Return the validation error message
        return f"Validation Error: {validated}"


@tool
def customer_lead_creation(name    : Annotated[str,"Customer name in lower case"],
                           phone   : Annotated[str,"Customer phone number in 10 digits"],
                           civil_id: Annotated[str,"Customer civil ID in 12 digits"],
                           email   : Annotated[str,"Customer email address"],
                           model   : Annotated[str,"Car model"],
                           variant : Annotated[str,"Car variant"]) -> str:
    """
    Creates a lead and links it to a customer in the Neo4j database.

    Parameters:
    - name: Customer's name (mandatory).
    - phone: Customer's phone number (mandatory).
    - civil_id: Customer's civil ID (mandatory).
    - email: Customer's email (mandatory).
    - model: The car model the customer is interested in (mandatory).
    - variant: The car variant (mandatory).

    Returns:
    - A message confirming lead creation or an error message.
    """
    
    # Helper function to handle null/empty strings
    def get_value(attr):
        return None if attr is None or attr.strip() == "" else attr

    # Check for missing parameters and prompt lead agent accordingly
    missing_params = []
    if not get_value(name):
        missing_params.append("Name")
    if not get_value(phone):
        missing_params.append("Phone number")
    if not get_value(civil_id):
        missing_params.append("Civil ID")
    if not get_value(email):
        missing_params.append("Email address")
    if not get_value(model):
        missing_params.append("Model")
    if not get_value(variant):
        missing_params.append("Variant")

    if missing_params:
        # Return a tool message asking the lead agent to prompt the user for missing details
        return (
            f"Error: Missing required details: {', '.join(missing_params)}. "
            "Please ask the user to provide the missing information."
        )

    # Validate email, phone, and civil ID
    if not validate_email_address(email):
        return "Error: Invalid email address. Please provide a valid email."
    if not validate_phone_number(phone):
        return "Error: Invalid phone number. Please provide a valid phone number."
    if not validate_civil_id(civil_id):
        return "Error: Invalid civil ID. Please provide a valid civil ID."

    # Proceed with creating the lead
    query = """
        MERGE (l:Customer {phone_number: $mobile})
        ON CREATE SET l.createdAt = $createdAt,
                      l.id = apoc.create.uuid()
        SET l.name = $name,
            l.email = $email,
            l.model = $model,
            l.variant = $variant,
            l.civil_id = $civil_id
        
        WITH l
        MERGE (c:Lead {id: l.id})
        ON CREATE SET c.createdAt = $createdAt
        SET c.name = $name, 
            c.phone_number = $mobile, 
            c.email = $email, 
            c.model = $model,
            c.variant = $variant,
            c.level = "High"
        MERGE (l)-[:CUSTOMER_OF_LEAD]->(c)
        
        WITH c
        MATCH (m:Model {name: $model})
        MERGE (c)-[:PREFERENCE]->(m)
    """
    
    params = {
        "name": name.capitalize(),
        "mobile": phone,
        "email": email,
        "createdAt": datetime.now().isoformat(),
        "variant": variant,
        "model": model,
        "civil_id": civil_id
    }

    try:
        # Execute the query on the Neo4j database
        test_graph.query(query, params)

        # Return success message with lead details
        return (
            f"Lead successfully created for {name.capitalize()}.\n"
            f"Customer Info:\n"
            f"Name: {name.capitalize()}\n"
            f"Phone: {phone}\n"
            f"Email: {email}\n"
            f"Model: {model} (Variant: {variant})\n"
            f"Civil ID: {civil_id}\n"
            f"Lead Level: High\n"
            f"Created At: {params['createdAt']}"
        )

    except Exception as e:
        # Catch any exceptions during the database operation and return an error message
        return f"Error: Failed to create lead due to: {str(e)}."
