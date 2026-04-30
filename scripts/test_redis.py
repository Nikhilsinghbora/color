"""Quick Redis connection test."""
import asyncio
import redis.asyncio as aioredis


async def main():
    url = "rediss://default:AZ7YAAIgcDEzYTQzYmQ4NDg3OTc0OWJhYjAxZDEzYTgwZDdhMzg2Zg@famous-burro-40664.upstash.io:6379"
    client = aioredis.from_url(url, decode_responses=True)
    try:
        pong = await client.ping()
        print(f"Redis ping: {pong}")
        await client.set("test_key", "hello")
        val = await client.get("test_key")
        print(f"Redis get: {val}")
        await client.delete("test_key")
        print("Redis connection OK!")
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
