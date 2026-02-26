import asyncio
from core.engine import VideoEngine

async def test():
    print("Testing VideoEngine...")
    engine = VideoEngine(user_data_dir="browser_session/9462", headless=True)
    try:
        page = await engine.launch()
        print("Engine launched.")
        
        is_logged = await engine.is_logged_in()
        print(f"Is logged in: {is_logged}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await engine.close()
        print("Engine closed.")

if __name__ == "__main__":
    asyncio.run(test())
