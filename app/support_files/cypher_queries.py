
# Customer existence query
customer_existance_query = """
MATCH (c:Customer) 
WHERE toLower(c.name) CONTAINS toLower($customer_name) 
RETURN c.name as customer_name, c.phone_number as phone_number
"""

# Query for check whether phone number exist or not
is_phone_number_exist_query = """
MATCH (l:Lead) 
WHERE l.phone_number = $phone_number 
RETURN l.name as corresponding_customer
"""

is_civil_id_exist_query = """
MATCH (c:Customer) 
WHERE c.civil_id = $civil_id 
RETURN c.name as corresponding_customer
"""

is_emaild_exist_query = """
MATCH (c:Customer)
WHERE c.email = $customer_email
RETURN c.name as corresponding_customer
"""