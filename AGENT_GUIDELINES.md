# GraphRAG Contract Review Guidelines

## Key Components
- Neo4j graph database
- GraphRAG for retrieval
- OpenAI for text processing
- Azure for PDF extraction

## Workflow
1. Process PDFs with `ingest.sh`
2. Build graph with `create_graph_from_json_azure.py`
3. Query with `app_streamlit.py` or `app_graphrag.py`

## Common Issues
- Relationship variables must be defined before accessing properties
- Check date formatting in Cypher queries
- Use templates in `/templates` directory

## Core Files
- `ContractService.py`: Main service with Neo4j schema
- `test_service.py`: Testing functionality
- `.env`: API keys and connection strings
