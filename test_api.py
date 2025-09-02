#!/usr/bin/env python3
"""
Test script for the Azure Service Bus Event Generator API
"""

import asyncio
import json
import sys
from datetime import datetime
from typing import Dict, Any

import httpx

# Configuration
BASE_URL = "http://localhost:8000"
API_KEY = "dev-api-key-123"

async def test_health_endpoint():
    """Test the health check endpoint"""
    print("Testing health endpoint...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/health")
            response.raise_for_status()
            
            health_data = response.json()
            print(f"✅ Health check passed: {health_data['status']}")
            print(f"   Service Bus connected: {health_data['service_bus_connected']}")
            return True
            
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            return False

async def test_create_event():
    """Test creating a single event"""
    print("\nTesting single event creation...")
    
    event_payload = {
        "event_type": "test_event",
        "data": {
            "message": "Hello from test script",
            "timestamp": datetime.utcnow().isoformat(),
            "test_id": "test-001"
        },
        "source": "test_script",
        "correlation_id": f"test-{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{BASE_URL}/events",
                json=event_payload,
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": API_KEY
                }
            )
            response.raise_for_status()
            
            result = response.json()
            print(f"✅ Event created successfully")
            print(f"   Event ID: {result['event_id']}")
            print(f"   Correlation ID: {result['correlation_id']}")
            return True
            
        except Exception as e:
            print(f"❌ Event creation failed: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"   Response: {e.response.text}")
            return False

async def test_batch_events():
    """Test creating multiple events in batch"""
    print("\nTesting batch event creation...")
    
    batch_payload = [
        {
            "event_type": "user_action",
            "data": {
                "user_id": "user-123",
                "action": "login",
                "timestamp": datetime.utcnow().isoformat()
            },
            "source": "web_app",
            "correlation_id": f"batch-{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}-1"
        },
        {
            "event_type": "system_event",
            "data": {
                "event": "startup",
                "version": "1.0.0",
                "timestamp": datetime.utcnow().isoformat()
            },
            "source": "system",
            "correlation_id": f"batch-{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}-2"
        },
        {
            "event_type": "business_event",
            "data": {
                "order_id": "order-456",
                "amount": 99.99,
                "currency": "USD",
                "timestamp": datetime.utcnow().isoformat()
            },
            "source": "ecommerce",
            "correlation_id": f"batch-{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}-3"
        }
    ]
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{BASE_URL}/events/batch",
                json=batch_payload,
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": API_KEY
                }
            )
            response.raise_for_status()
            
            result = response.json()
            print(f"✅ Batch events created successfully")
            print(f"   Total: {result['total_count']}")
            print(f"   Successful: {result['successful_count']}")
            print(f"   Failed: {result['failed_count']}")
            return True
            
        except Exception as e:
            print(f"❌ Batch event creation failed: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"   Response: {e.response.text}")
            return False

async def test_rate_limiting():
    """Test rate limiting by sending multiple requests quickly"""
    print("\nTesting rate limiting...")
    
    event_payload = {
        "event_type": "rate_limit_test",
        "data": {"test": "rate limiting"},
        "source": "test_script"
    }
    
    async with httpx.AsyncClient() as client:
        success_count = 0
        rate_limited_count = 0
        
        # Send 5 requests quickly
        for i in range(5):
            try:
                response = await client.post(
                    f"{BASE_URL}/events",
                    json=event_payload,
                    headers={
                        "Content-Type": "application/json",
                        "X-API-Key": API_KEY
                    }
                )
                response.raise_for_status()
                success_count += 1
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    rate_limited_count += 1
                else:
                    print(f"❌ Unexpected error: {e}")
            except Exception as e:
                print(f"❌ Request failed: {e}")
        
        print(f"✅ Rate limiting test completed")
        print(f"   Successful requests: {success_count}")
        print(f"   Rate limited requests: {rate_limited_count}")
        return True

async def test_authentication():
    """Test authentication with invalid API key"""
    print("\nTesting authentication...")
    
    event_payload = {
        "event_type": "auth_test",
        "data": {"test": "authentication"},
        "source": "test_script"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            # Test with invalid API key
            response = await client.post(
                f"{BASE_URL}/events",
                json=event_payload,
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": "invalid-key"
                }
            )
            
            if response.status_code == 401:
                print("✅ Authentication correctly rejected invalid API key")
                return True
            else:
                print(f"❌ Authentication test failed - expected 401, got {response.status_code}")
                return False
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                print("✅ Authentication correctly rejected invalid API key")
                return True
            else:
                print(f"❌ Authentication test failed - expected 401, got {e.response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Authentication test failed: {e}")
            return False

async def main():
    """Run all tests"""
    print("🚀 Starting API tests...")
    print(f"Base URL: {BASE_URL}")
    print(f"API Key: {API_KEY}")
    print("=" * 50)
    
    tests = [
        ("Health Check", test_health_endpoint),
        ("Single Event", test_create_event),
        ("Batch Events", test_batch_events),
        ("Rate Limiting", test_rate_limiting),
        ("Authentication", test_authentication)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary:")
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⏹️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Tests crashed: {e}")
        sys.exit(1)
