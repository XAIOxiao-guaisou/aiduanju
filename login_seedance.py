import asyncio
from seedance_agent import SeedanceVisualAgent

async def login():
    agent = SeedanceVisualAgent(headless=False)
    await agent.login_only(timeout_minutes=5)

if __name__ == "__main__":
    asyncio.run(login())
