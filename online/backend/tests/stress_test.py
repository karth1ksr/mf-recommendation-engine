import asyncio
import httpx
import time
import uuid
import sys
from loguru import logger

# Configuration
BASE_URL = "http://localhost:8000"
CONNECT_ENDPOINT = f"{BASE_URL}/api/v1/connect"
HEALTH_ENDPOINT = f"{BASE_URL}/health"
NUM_USERS = 30
CONCURRENT_REQUESTS = 5 # How many to start at once to avoid overwhelming the local machine's socket limit

async def simulate_user(user_id):
    """
    Simulates a single user connecting to the bot.
    """
    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info(f"User {user_id}: Attempting to connect...")
            response = await client.post(CONNECT_ENDPOINT)
            
            if response.status_code == 200:
                data = response.json()
                duration = time.time() - start_time
                logger.success(f"User {user_id}: Connected successfully in {duration:.2f}s. Room: {data.get('room_url')}")
                return {
                    "user_id": user_id,
                    "status": "success",
                    "duration": duration,
                    "session_id": data.get("session_id")
                }
            else:
                logger.error(f"User {user_id}: Failed to connect. Status: {response.status_code}, Detail: {response.text}")
                return {"user_id": user_id, "status": "failed", "error": response.text}
    except Exception as e:
        logger.error(f"User {user_id}: Exception occurred: {str(e)}")
        return {"user_id": user_id, "status": "error", "error": str(e)}

async def run_stress_test():
    """
    Runs the stress test for the specified number of users.
    """
    logger.info(f"Starting stress test for {NUM_USERS} concurrent users...")
    
    # Check health first
    async with httpx.AsyncClient() as client:
        try:
            health = await client.get(HEALTH_ENDPOINT)
            if health.status_code == 200:
                logger.info("Backend is healthy. Starting test.")
            else:
                logger.warning(f"Backend health check failed: {health.status_code}. Proceeding anyway...")
        except Exception:
            logger.error("Backend unreachable. Please ensure the server is running on http://localhost:8000")
            return

    tasks = []
    # We can use a semaphore to control concurrency of the connect calls themselves
    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

    async def sem_simulate(u_id):
        async with semaphore:
            return await simulate_user(u_id)

    for i in range(NUM_USERS):
        tasks.append(sem_simulate(i + 1))

    results = await asyncio.gather(*tasks)

    # Summary
    successes = [r for r in results if r["status"] == "success"]
    failures = [r for r in results if r["status"] != "success"]
    
    logger.info("=== Stress Test Summary ===")
    logger.info(f"Total Users Sampled: {NUM_USERS}")
    logger.success(f"Successful Connections: {len(successes)}")
    logger.error(f"Failed Connections: {len(failures)}")
    
    if successes:
        avg_time = sum(r["duration"] for r in successes) / len(successes)
        max_time = max(r["duration"] for r in successes)
        min_time = min(r["duration"] for r in successes)
        logger.info(f"Average Connection Time: {avg_time:.2f}s")
        logger.info(f"Min Connection Time: {min_time:.2f}s")
        logger.info(f"Max Connection Time: {max_time:.2f}s")

    # Keep the sessions alive for a bit to see if bots stay running?
    # In a real test, we might want to wait here.
    logger.info("Test completed. Note: Bots remain running in the background until they time out or are deleted.")

if __name__ == "__main__":
    try:
        asyncio.run(run_stress_test())
    except KeyboardInterrupt:
        logger.info("Test interrupted.")
