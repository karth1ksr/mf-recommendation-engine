import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from loguru import logger
from dotenv import load_dotenv

# Import our modules
from online.engine.user_snapshot import UserSnapshot
from online.engine.request_normalizer import RequestNormalizer
from online.engine.recommender import RecommendationEngine
from online.engine.orchestrator import handle_user_input

# Load environment variables (for GEMINI_API_KEY)
load_dotenv()

async def run_integration_test():
    """
    Integration test for the full online flow using local MongoDB.
    
    Ensure:
    1. Local MongoDB is running.
    2. Database 'mf_recommender' (or your name) has collection 'fund_metrics'.
    3. GEMINI_API_KEY is set in environment or .env file.
    """
    
    # 1. Setup Database Connection
    # Update the connection string if your local Mongo uses a different port or credentials
    MONGO_URI = "mongodb://localhost:27017"
    DB_NAME = "mf_engine"
    
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    
    print(f"\n--- Testing Connection to MongoDB: {DB_NAME} ---")
    try:
        # Quick check if collection exists and has data
        count = await db.fund_metrics.count_documents({})
        print(f"Funds found in 'fund_metrics' collection: {count}")
        if count == 0:
            print("WARNING: 'fund_metrics' collection is empty. Recommendations will return empty lists.")
    except Exception as e:
        print(f"ERROR: Could not connect to MongoDB: {e}")
        return

    # 2. Initialize Components
    snapshot = UserSnapshot()
    normalizer = RequestNormalizer()
    recommender = RecommendationEngine(db)
    
    # 3. Simulate Interactive User Session
    user_inputs = [
        "I need some investment advice",                        # Step 1: Initialize
        "I am looking for high risk options",                   # Step 2: Provide Risk
        "I want to invest for at least 10 years",               # Step 3: Provide Horizon
        "Suggest some equity funds"                             # Step 4: Provide Category -> Triggers Recommendation
    ]

    print("\n--- Starting Live Integration Simulation ---\n")

    for i, text in enumerate(user_inputs, 1):
        print(f"Step {i} | User Input: '{text}'")
        
        # Process input through the orchestrator
        response = await handle_user_input(text, snapshot, normalizer, recommender)
        
        if response["type"] == "question":
            print(f"System Question: {response['text']}")
            print(f"Missing Field: {response['question_intent']}")
            print("-" * 30)
            
        elif response["type"] == "recommendation":
            print(f"\n✅ RECOMMENDATION GENERATED!")
            print(f"Number of funds found: {len(response['data'])}")
            
            print("\n--- Top Funds Scored ---")
            for fund in response['data']:
                print(f"- {fund.get('scheme_name')} | Score: {fund.get('recommendation_score')}")
            
            print("\n--- LLM Explanation ---")
            print(response.get('explanation', 'No explanation provided.'))
            print("-" * 30)
            break
        
        elif response["type"] == "comparison":
            print(f"System: {response['message']}")

    # Close DB connection
    client.close()

if __name__ == "__main__":
    # Ensure current directory is in path to import online module correctly
    import sys
    sys.path.append(os.getcwd())
    
    asyncio.run(run_integration_test())
