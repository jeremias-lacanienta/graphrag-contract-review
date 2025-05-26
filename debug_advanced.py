import logging
import sys
import asyncio
from ContractService import ContractSearchService
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USER = os.getenv('NEO4J_USERNAME', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')

async def main():
    service = ContractSearchService(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    question = "What are the incorporation states for parties in the Master Franchise Agreement?"
    logger.debug(f"Question: {question}")
    try:
        result = await service.answer_aggregation_question(question)
        logger.debug(f"Result: {result}")
        print(result)
    except Exception as e:
        logger.exception(f"Error: {str(e)}")
        
    # Now dump the raw response structure
    try:
        from neo4j_graphrag.retrievers import Text2CypherRetriever
        text2cypher_retriever = Text2CypherRetriever(
            llm=service._llm,
            driver=service._driver,
            neo4j_schema="dummy"
        )
        
        result = text2cypher_retriever.search(query_text=question)
        logger.debug("Raw result type: %s", type(result))
        logger.debug("Result attributes: %s", dir(result))
        if hasattr(result, 'items'):
            logger.debug("Items type: %s", type(result.items))
            logger.debug("First item type: %s", type(result.items[0]) if result.items else "No items")
            if result.items:
                logger.debug("First item attributes: %s", dir(result.items[0]))
                for i, item in enumerate(result.items):
                    logger.debug("Item %d: %s", i, item)
                    
    except Exception as e:
        logger.exception(f"Debug error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
