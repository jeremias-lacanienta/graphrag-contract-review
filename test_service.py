import asyncio
from ContractService import ContractSearchService
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Neo4j credentials from environment
NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USER = os.getenv('NEO4J_USERNAME', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'password')

async def test_service():
    """Test the ContractSearchService with various questions"""
    
    # Initialize service
    service = ContractSearchService(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    
    # Test questions
    questions = [
        "What agreements are in the database?",
        "What are the incorporation states for parties in the Master Franchise Agreement?",
        "What is the Stock Purchase Agreement about?",
        "Tell me about the Revenue Sharing clause",
        "Who are the parties in the merger agreement?"
    ]
    
    # Run tests
    for question in questions:
        print(f"\n\n== TESTING QUESTION: {question} ==")
        try:
            result = await service.answer_aggregation_question(question)
            print(f"RESULT: {result}")
        except Exception as e:
            import traceback
            print(f"ERROR: {str(e)}")
            print("TRACEBACK:")
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_service())
