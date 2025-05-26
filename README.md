# GraphRAG in Commercial Contract Review

This repository contains all of the code mentioned in [GraphRAG in Commercial Contract Review](https://medium.com/@edward.sandoval.2000/graphrag-in-commercial-contract-review-7d4a6caa6eb5).

## New: Dual Environment Setup

This repository now offers two separate environments to avoid dependency conflicts:

1. **Original environment (semantic-kernel based)**: Uses semantic-kernel with pydantic v1.x
2. **GraphRAG-only environment**: Uses neo4j_graphrag with pydantic v2.x

### GraphRAG-only Environment Setup

To use only the neo4j_graphrag functionality without semantic-kernel:

```bash
# Run the GraphRAG setup and demo script
./setup_and_run_graphrag.sh
```

This script:
- Creates a dedicated virtual environment (.venv_graphrag)
- Installs the necessary dependencies from requirements_graphrag.txt
- Runs all available commands in sequence with proper formatting

For individual commands:
```bash
# Run a specific command
./run_graphrag.sh <command> [arguments]
```

Example usage:
```bash
# Get details of a specific contract
./run_graphrag.sh get_contract 123

# Get contracts for a specific party
./run_graphrag.sh get_contracts_by_party 'Acme Corp'

# Get contracts with a specific clause type
./run_graphrag.sh get_contracts_with_clause_type 'TERMINATION'

# Search for contracts with similar text in clauses
./run_graphrag.sh get_contracts_similar_text 'payment terms'

# Answer questions using the aggregation of contracts
./run_graphrag.sh answer_aggregation_question 'How many contracts are governed by Delaware law?'
```

### Web Interface with Streamlit

A Streamlit-based web interface is now available for easier interaction:

```bash
# Launch the Streamlit web interface
./run_streamlit.sh
```

The web interface provides:
- A clickable menu for all available commands
- Chat-like input interface for entering queries
- Formatted display of results
- Interactive exploration of contracts

![Streamlit Interface](images/streamlit_view.png)

### Enhanced Output Formatting

The GraphRAG-only implementation now uses Jinja2 templates for better display formatting:

- Color-coded terminal output
- Structured display of contract information
- Deduplication of parties, clauses, and excerpts
- Special formatting for different types of queries
- Clear presentation of aggregation question results

### Environment Cleanup

To clean up the environment and reset the Neo4j database:

```bash
# Run the cleaning script
./clear_all.sh
```

This script will:
- Remove all virtual environments
- Delete all nodes and relationships in the Neo4j database
- Reset any constraints or indexes

### Original Environment (with Semantic Kernel)

The original implementation with semantic-kernel is still available:

```bash
# Setup the original environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run the original console app
python app_console.py

# Or run the agent
python test_agent.py

# Or run the Streamlit app
streamlit run app.py
```

## Project Structure

- **GraphRAG-only Implementation**:
  - `app_graphrag.py`: Pure neo4j_graphrag implementation without semantic-kernel
  - `run_graphrag.sh`: Script to set up dedicated environment and run app_graphrag.py
  - `requirements_graphrag.txt`: Dependencies for neo4j_graphrag
  - `ContractPluginGraphrag.py`: Non-semantic-kernel version of the contract plugin

- **Shared Components**:
  - `ContractService.py`: Service layer with Neo4j and neo4j_graphrag operations
  - `AgreementSchema.py`: Data models for agreements and contracts

- **Original Implementation**:
  - `app_console.py`: Original console app using semantic-kernel
  - `app.py`: Streamlit interface using semantic-kernel
  - `test_agent.py`: Simple terminal-based agent with semantic-kernel
  - `ContractPlugin.py`: Contract plugin using semantic-kernel

## Contract Review - GraphRAG-based approach

The GraphRAG-based approach described in the blog post goes beyond the traditional chunk-based RAG, focusing instead on targeted information extraction from the contracts (LLM + Prompt) to create a knowledge graph representation (LLM + Neo4J), a simple set of data retrieval functions (in Python using Cypher, Text to Cypher, Vector Search retrievers) and ultimately a Q&A agent (Semantic Kernel) capable of handling complex questions

The diagram below illustrates the approach

![4-stage-approach](./images/4-stage-approach%20.png)
The 4-stage GraphRAG approach: From question-based extraction -> knowledge graph model -> GraphRAG retrieval -> Q&A Agent


The four steps are:
1. Extracting Relevant Information from Contracts (LLM + Contract)
2. Storing information extracted into a Knowledge Graph (Neo4j)
3. Developing simple KG Data Retrieval Functions (Python)
4. Building a Q&A Agent handling complex questions (Semantic Kernel, LLM, Neo4j)

[Rest of original README content...]
