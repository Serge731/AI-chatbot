import requests
import time

def test_backend_speed():
    url = "http://127.0.0.1:8000/auth/login"
    test_data = {
        "username": "testuser",  # use a real username from your DB
        "password": "testpassword"  # use the correct password
    }
    
    start_time = time.time()
    
    try:
        response = requests.post(url, json=test_data, timeout=10)
        end_time = time.time()
        
        print(f"Response time: {(end_time - start_time) * 1000:.2f}ms")
        print(f"Status code: {response.status_code}")
        print(f"Response: {response.text}")
        
    except requests.exceptions.Timeout:
        print("Request timed out after 10 seconds!")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_backend_speed()