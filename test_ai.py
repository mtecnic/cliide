#!/usr/bin/env python3
"""Test AI integration."""

import asyncio
from cliide.ai.vllm_client import get_client
from cliide.ai.code_actions import CodeActions
from cliide.core.config import get_config


async def test_connection():
    """Test VLLM connection."""
    print("Testing VLLM connection...")
    client = get_client()

    try:
        connected = await client.check_connection()
        if connected:
            print("✓ Connected to VLLM server")
            return True
        else:
            print("✗ Cannot connect to VLLM server")
            return False
    except Exception as e:
        print(f"✗ Connection error: {e}")
        return False


async def test_simple_completion():
    """Test simple AI completion."""
    print("\nTesting simple completion...")
    client = get_client()

    try:
        response = await client.complete("Say 'Hello from cliide!' and nothing else.")
        print(f"✓ AI Response: {response[:100]}...")
        return True
    except Exception as e:
        print(f"✗ Completion error: {e}")
        return False


async def test_streaming():
    """Test streaming completion."""
    print("\nTesting streaming...")
    client = get_client()

    try:
        print("AI: ", end="", flush=True)
        async for chunk in client.stream_complete("Count to 5"):
            print(chunk, end="", flush=True)
        print("\n✓ Streaming works")
        return True
    except Exception as e:
        print(f"\n✗ Streaming error: {e}")
        return False


async def test_code_actions():
    """Test code actions."""
    print("\nTesting code actions...")
    actions = CodeActions()

    test_code = """
def factorial(n):
    if n == 0:
        return 1
    return n * factorial(n - 1)
"""

    try:
        print("Explaining code...")
        response = ""
        async for chunk in actions.explain_code(test_code, "python"):
            response += chunk

        if response:
            print(f"✓ Explanation received ({len(response)} chars)")
            return True
        else:
            print("✗ No response")
            return False
    except Exception as e:
        print(f"✗ Code action error: {e}")
        return False


async def main():
    """Run all tests."""
    print("=" * 50)
    print("cliide AI Integration Tests")
    print("=" * 50)

    config = get_config()
    print(f"\nVLLM Config:")
    print(f"  URL: {config.vllm.base_url}")
    print(f"  Model: {config.vllm.model}")
    print()

    tests = [
        test_connection(),
        test_simple_completion(),
        test_streaming(),
        test_code_actions(),
    ]

    results = await asyncio.gather(*tests, return_exceptions=True)

    print("\n" + "=" * 50)
    passed = sum(1 for r in results if r is True)
    print(f"Tests passed: {passed}/{len(tests)}")
    print("=" * 50)

    return all(results)


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTests interrupted")
        exit(1)
