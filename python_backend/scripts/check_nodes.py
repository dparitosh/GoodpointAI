import asyncio
from neo4j import AsyncGraphDatabase
import os

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

async def main():
    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        await driver.verify_connectivity()
        result = await driver.execute_query('MATCH (n) RETURN count(n) AS c', database_=NEO4J_DATABASE)
        count = result.records[0]['c']
        print(f"Node count: {count}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await driver.close()

if __name__ == "__main__":
    asyncio.run(main())