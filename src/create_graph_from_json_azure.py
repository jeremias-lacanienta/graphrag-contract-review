from neo4j import GraphDatabase
import json
import os
import sys
from openai import AzureOpenAI
from dotenv import load_dotenv

# Add the parent directory to sys.path to enable imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables
load_dotenv()

# Configure Azure OpenAI
AZURE_OPENAI_API_KEY = os.getenv('AZURE_OPENAI_API_KEY')
AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT', 'text-embedding-3-small')

# Check if Azure OpenAI configuration is available
if not AZURE_OPENAI_API_KEY or not AZURE_OPENAI_ENDPOINT:
    print("Azure OpenAI configuration not found. Please add to your .env file:")
    print("AZURE_OPENAI_API_KEY=your-key")
    print("AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/")
    print("AZURE_OPENAI_EMBEDDING_DEPLOYMENT=your-embedding-deployment-name (defaults to text-embedding-3-small)")
    exit(1)

# Initialize Azure OpenAI client
client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    api_version="2023-05-15",
    azure_endpoint=AZURE_OPENAI_ENDPOINT
)

CREATE_GRAPH_STATEMENT = """
WITH $data AS data
WITH data.agreement as a

// todo proper global id for the agreement, perhaps from filename
MERGE (agreement:Agreement {contract_id: a.contract_id})
ON CREATE SET 
  agreement.name = a.name,
  agreement.effective_date = a.effective_date,
  agreement.expiration_date = a.expiration_date,
  agreement.agreement_type = a.agreement_type,
  agreement.renewal_term = a.renewal_term,
  agreement.most_favored_country = a.governing_law.most_favored_country,
  agreement.filename = a.filename
  //agreement.Notice_period_to_Terminate_Renewal = a.Notice_period_to_Terminate_Renewal
  

MERGE (gl_country:Country {name: a.governing_law.country})
MERGE (agreement)-[gbl:GOVERNED_BY_LAW]->(gl_country)
SET gbl.state = a.governing_law.state


FOREACH (party IN a.parties |
  // todo proper global id for the party
  MERGE (p:Organization {name: party.name})
  MERGE (p)-[ipt:IS_PARTY_TO]->(agreement)
  SET ipt.role = party.role
  MERGE (country_of_incorporation:Country {name: party.incorporation_country})
  MERGE (p)-[incorporated:INCORPORATED_IN]->(country_of_incorporation)
  SET incorporated.state = party.incorporation_state
)

WITH a, agreement, [clause IN a.clauses WHERE clause.exists = true] AS valid_clauses
FOREACH (clause IN valid_clauses |
  CREATE (cl:ContractClause {type: clause.type})
  MERGE (agreement)-[clt:HAS_CLAUSE]->(cl)
  SET clt.type = clause.type
  // ON CREATE SET c.excerpts = clause.excerpts
  FOREACH (excerpt IN clause.excerpts |
    MERGE (cl)-[:HAS_EXCERPT]->(e:Excerpt {text: excerpt})
  )
  //link clauses to a Clause Type label
  MERGE (clType:ClauseType{name: clause.type})
  MERGE (cl)-[:HAS_TYPE]->(clType)
)"""

CREATE_VECTOR_INDEX_STATEMENT = """
CREATE VECTOR INDEX excerpt_embedding IF NOT EXISTS 
    FOR (e:Excerpt) ON (e.embedding) 
    OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`:'cosine'}} 
"""

CREATE_FULL_TEXT_INDICES = [
    ("excerptTextIndex", "CREATE FULLTEXT INDEX excerptTextIndex IF NOT EXISTS FOR (e:Excerpt) ON EACH [e.text]"),
    ("agreementTypeTextIndex", "CREATE FULLTEXT INDEX agreementTypeTextIndex IF NOT EXISTS FOR (a:Agreement) ON EACH [a.agreement_type]"),
    ("clauseTypeNameTextIndex", "CREATE FULLTEXT INDEX clauseTypeNameTextIndex IF NOT EXISTS FOR (ct:ClauseType) ON EACH [ct.name]"),
    ("clauseNameTextIndex", "CREATE FULLTEXT INDEX contractClauseTypeTextIndex IF NOT EXISTS FOR (c:ContractClause) ON EACH [c.type]"),
    ("organizationNameTextIndex", "CREATE FULLTEXT INDEX organizationNameTextIndex IF NOT EXISTS FOR (o:Organization) ON EACH [o.name]"),
    ("contractIdIndex","CREATE INDEX agreementContractId IF NOT EXISTS FOR (a:Agreement) ON (a.contract_id) ")
]

# Function to get the highest existing contract_id
def get_max_contract_id(driver):
    query = """
    MATCH (a:Agreement)
    RETURN COALESCE(MAX(a.contract_id), 0) as max_id
    """
    result = driver.execute_query(query)
    return result.records[0].get("max_id") if result.records else 0

def index_exists(driver, index_name):
    check_index_query = "SHOW INDEXES WHERE name = $index_name"
    result = driver.execute_query(check_index_query, {"index_name": index_name})
    return len(result.records) > 0

def create_full_text_indices(driver):
    with driver.session() as session:
        for index_name, create_query in CREATE_FULL_TEXT_INDICES:
            if not index_exists(driver, index_name):
                print(f"Creating index: {index_name}")
                driver.execute_query(create_query)
            else:
                print(f"Index {index_name} already exists.")

# Function to generate embeddings using Azure OpenAI
def generate_azure_embeddings(texts):
    try:
        response = client.embeddings.create(
            input=texts,
            model=AZURE_OPENAI_EMBEDDING_DEPLOYMENT
        )
        # Extract embeddings from the response
        embeddings = [embedding.embedding for embedding in response.data]
        return embeddings
    except Exception as e:
        print(f"Error generating embeddings: {e}")
        raise

# Function to get all excerpts that need embeddings
def get_excerpts_without_embeddings(driver):
    query = """
    MATCH (e:Excerpt) 
    WHERE e.text IS NOT NULL AND e.embedding IS NULL
    RETURN id(e) AS id, e.text AS text
    """
    result = driver.execute_query(query)
    return [(record["id"], record["text"]) for record in result.records]

# Function to update embeddings in batches
def update_embeddings_in_batches(driver, excerpt_ids, embeddings):
    query = """
    UNWIND $batch AS item
    MATCH (e:Excerpt) 
    WHERE id(e) = item.id
    SET e.embedding = item.embedding
    """
    
    batch = [{"id": id, "embedding": embedding} for id, embedding in zip(excerpt_ids, embeddings)]
    driver.execute_query(query, {"batch": batch})

def main():
    # Connect to Neo4j
    NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    NEO4J_USER = os.getenv('NEO4J_USERNAME', 'neo4j')
    NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')
    JSON_CONTRACT_FOLDER = '../data/output/'

    if not NEO4J_PASSWORD:
        print("Neo4j password not found. Please set NEO4J_PASSWORD in your .env file")
        exit(1)

    print(f"Connecting to Neo4j at {NEO4J_URI}...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    # Get the next available contract_id
    next_contract_id = get_max_contract_id(driver) + 1
    print(f"Starting with contract_id: {next_contract_id}")

    # Process JSON files and create graph
    json_contracts = [filename for filename in os.listdir(JSON_CONTRACT_FOLDER) if filename.endswith('.json')]
    print(f"Found {len(json_contracts)} JSON files to process")
    
    for json_contract in json_contracts:
        # Extract the original PDF filename (remove the .json extension)
        pdf_name = json_contract.replace('.json', '')
        
        # Check if a contract with this filename already exists
        check_existing_query = """
        MATCH (a:Agreement {filename: $filename})
        RETURN a.contract_id as contract_id
        """
        result = driver.execute_query(check_existing_query, {"filename": pdf_name})
        
        contract_id = None
        if result.records:
            # Use the existing contract_id if it exists
            contract_id = result.records[0].get("contract_id")
            print(f"Updating existing contract for {pdf_name} with ID {contract_id}")
            
            # Delete existing clauses and relationships for this contract
            # This keeps the Agreement node but removes related data to be replaced
            cleanup_query = """
            MATCH (a:Agreement {filename: $filename})-[r:HAS_CLAUSE]->(cc:ContractClause)
            WITH a, r, cc
            OPTIONAL MATCH (cc)-[r2]->(n)
            DETACH DELETE r2, cc
            """
            driver.execute_query(cleanup_query, {"filename": pdf_name})
        else:
            # Use the next available contract_id
            contract_id = next_contract_id
            next_contract_id += 1
            print(f"Creating new contract for {pdf_name} with ID {contract_id}")
        
        print(f"Processing {json_contract}...")
        with open(JSON_CONTRACT_FOLDER + json_contract, 'r') as file:
            json_string = file.read()
            json_data = json.loads(json_string)
            agreement = json_data['agreement']
            agreement['contract_id'] = contract_id
            agreement['filename'] = pdf_name  # Store the filename to identify this contract
            
            # Convert clause_type to type in all clauses for consistency
            if 'clauses' in agreement:
                for clause in agreement['clauses']:
                    if 'clause_type' in clause:
                        clause['type'] = clause['clause_type']
            
            # Convert agreement_name to name for consistency
            if 'agreement_name' in agreement and 'name' not in agreement:
                agreement['name'] = agreement['agreement_name']
            
            driver.execute_query(CREATE_GRAPH_STATEMENT, data=json_data)
    
    # Create indices
    print("Creating indices...")
    create_full_text_indices(driver)
    driver.execute_query(CREATE_VECTOR_INDEX_STATEMENT)
    
    # Generate embeddings using Azure OpenAI
    print("Generating embeddings for contract excerpts...")
    
    # Get all excerpts that need embeddings
    excerpts_to_process = get_excerpts_without_embeddings(driver)
    
    if not excerpts_to_process:
        print("No excerpts need embeddings")
        driver.close()
        return
    
    print(f"Found {len(excerpts_to_process)} excerpts that need embeddings")
    
    # Process in batches of 20 to avoid rate limits
    batch_size = 20
    for i in range(0, len(excerpts_to_process), batch_size):
        batch = excerpts_to_process[i:i+batch_size]
        excerpt_ids = [item[0] for item in batch]
        texts = [item[1] for item in batch]
        
        print(f"Generating embeddings for batch {i//batch_size + 1}/{len(excerpts_to_process)//batch_size + 1} ({len(texts)} texts)...")
        
        try:
            embeddings = generate_azure_embeddings(texts)
            update_embeddings_in_batches(driver, excerpt_ids, embeddings)
            print(f"Successfully updated embeddings for batch")
        except Exception as e:
            print(f"Error processing batch: {e}")
    
    print("All embeddings generated and saved to Neo4j")
    driver.close()

if __name__ == '__main__':
    main()
