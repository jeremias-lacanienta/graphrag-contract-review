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

# Import the LLM formatter
from llm_formatter import format_result as llm_format_result

logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Suppress httpx INFO level logs
logging.getLogger("httpx").setLevel(logging.WARNING)

OPENAI_KEY = os.getenv('OPENAI_API_KEY')
NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USER = os.getenv('NEO4J_USERNAME', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')

def generate_user_question(command: str, args: List[str] = None, user_input: str = "") -> str:
    """
    Generate an appropriate user question based on the command type and arguments.
    This ensures the LLM formatter has a clear question to answer.
    
    Args:
        command: The command being executed
        args: Command arguments (for CLI usage)
        user_input: User input (for Streamlit usage)
        
    Returns:
        A well-formed question for the LLM formatter
    """
    # Use user_input if it looks like a proper question (contains question words or is long enough)
    if user_input and (any(word in user_input.lower() for word in ['what', 'which', 'how', 'when', 'where', 'why', 'who']) or len(user_input.split()) > 3):
        return user_input
    
    # Otherwise, generate a question based on command type
    param = user_input or (args[0] if args else "")
    
    if command == "get_contract":
        return f"What are the details of contract ID {param}?"
    elif command == "get_contracts_by_party":
        return f"What contracts involve the organization '{param}'?"
    elif command == "get_contracts_with_clause_type":
        return f"Which contracts contain '{param}' clauses?"
    elif command == "get_contracts_without_clause":
        return f"Which contracts do not contain '{param}' clauses?"
    elif command == "get_contract_excerpts":
        return f"What are the clause excerpts from contract ID {param}?"
    elif command == "get_contracts_similar_text":
        return f"Find contracts related to '{param}'"
    elif command == "search":
        return f"Search for contracts related to '{param}'"
    elif command == "answer_aggregation_question":
        return param  # For aggregation questions, the parameter IS the question
    else:
        return param or "Provide information about the contract data."

async def format_result(result: Any, command: str = None, args: List[str] = None) -> str:
    """
    Format query results into readable text using the LLM formatter.
    Answers are grounded in the user's specific question with precise evidence.
    
    Args:
        result: Query result from ContractService methods
        command: The command that was used (optional)
        args: The command arguments (optional)
        
    Returns:
        Formatted string output
    """
    # Generate appropriate user question based on command type
    user_question = generate_user_question(command, args)
    
    # Use the imported format_result function directly (it's already async)
    return await llm_format_result(result, command, user_question)

async def main():
    service = ContractSearchService(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    
    if len(sys.argv) < 2:
        logging.error("Missing command")
        sys.exit(1)
        
    command = sys.argv[1]
    # Convert hyphens to underscores for command compatibility
    command = command.replace('-', '_')
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
            clause_type_str = args[0]
            # Try to find the clause type by value first, then by name
            clause_type = clause_type_str
            for ct in ClauseType:
                if ct.value.lower() == clause_type_str.lower():
                    clause_type = ct
                    break
            result = await service.get_contracts_with_clause_type(clause_type)
        elif command == "get_contracts_without_clause" and args:
            clause_type_str = args[0]
            # Try to find the clause type by value first, then by name
            clause_type = clause_type_str
            for ct in ClauseType:
                if ct.value.lower() == clause_type_str.lower():
                    clause_type = ct
                    break
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
                print(await format_result(result, command, args))
                print("─" * 60)
            else:
                print(await format_result(result, command, args))
        else:
            print("No results found.")
            
    except Exception as e:
        print(f"Error: {str(e)}")
        logging.error(f"Error executing command: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
