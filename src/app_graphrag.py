"""
GraphRAG Contract Review Application

A command-line interface for reviewing and querying contract data using neo4j_graphrag
without semantic-kernel dependencies.
"""

import os
import sys
import json
import asyncio
import logging
from typing import Any, Dict, List, Union

from ContractService import ContractSearchService
from AgreementSchema import ClauseType

from dotenv import load_dotenv
load_dotenv()

# Import the template renderer
from template_renderer import format_result as render_template

logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

OPENAI_KEY = os.getenv('OPENAI_API_KEY')
NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USER = os.getenv('NEO4J_USERNAME', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')

def format_result(result: Any, command: str = None, args: List[str] = None) -> str:
    """
    Format query results into readable text using the template renderer.
    This is a wrapper around the template_renderer's format_result function.
    
    Args:
        result: Query result from ContractService methods
        command: The command that was used (optional)
        args: The command arguments (optional)
        
    Returns:
        Formatted string output
    """
    return render_template(result, command, args)

async def main():
    service = ContractSearchService(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    
    if len(sys.argv) < 2:
        logging.error("Missing command")
        sys.exit(1)
        
    command = sys.argv[1]
    args = sys.argv[2:]
    result = None
    is_aggregation_question = False
    question = ""

    # Skip help command without any action
    if command in ["help", "--help", "-h"]:
        sys.exit(0)

    try:
        # Consolidated command handling
        if command == "get_contract" and args:
            contract_id = int(args[0])
            result = await service.get_contract(contract_id)
        elif command == "get_contracts_by_party" and args:
            org = args[0]
            result = await service.get_contracts(org)
        elif command == "get_contracts_with_clause_type" and args:
            clause_type = ClauseType[args[0]] if hasattr(ClauseType, args[0]) else args[0]
            result = await service.get_contracts_with_clause_type(clause_type)
        elif command == "get_contracts_without_clause" and args:
            clause_type = ClauseType[args[0]] if hasattr(ClauseType, args[0]) else args[0]
            result = await service.get_contracts_without_clause(clause_type)
        elif command == "get_contract_excerpts" and args:
            contract_id = int(args[0])
            result = await service.get_contract_excerpts(contract_id)
        elif command == "answer_aggregation_question" and args:
            question = args[0]
            result = await service.answer_aggregation_question(question)
            is_aggregation_question = True
        elif command == "search" and args or command == "get_contracts_similar_text" and args:
            clause_text = args[0]
            result = await service.get_contracts_similar_text(clause_text)
            command = "get_contracts_similar_text"  # Ensure we use the correct formatter
        elif args:
            # Default behavior: Treat any unrecognized command with args as a text search
            clause_text = args[0] if args else command
            result = await service.get_contracts_similar_text(clause_text)
            if command != "get_contracts_similar_text":
                logging.info(f"Unrecognized command '{command}'. Using as search text.")
        else:
            logging.error("Missing arguments for command.")
            sys.exit(1)
        
        # Single print statement for all commands
        if result is not None:
            if is_aggregation_question:
                # Special handling for aggregation questions
                print("\n" + "─" * 60)
                print(f"Question: {question}")
                print("─" * 60)
                print(format_result(result, command, args))
                print("─" * 60)
            else:
                print(format_result(result, command, args))
        else:
            print("No results found.")
            
    except Exception as e:
        print(f"Error: {str(e)}")
        logging.error(f"Error executing command: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
