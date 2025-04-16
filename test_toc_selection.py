import requests
import os

print("Testing TOC selection functionality")

# Base URL for the application
base_url = "http://localhost:9000"

# Test connectivity
try:
    response = requests.get(base_url)
    print(f"Connection test: {'Success' if response.status_code == 200 else 'Failed'}")
except Exception as e:
    print(f"Connection failed: {e}")
    exit(1)

# Test file paths
lastenboek_path = os.path.join("uploads", "CoordinatedArchitectlastenboek.pdf")
meetstaat_path = os.path.join("uploads", "meetstaat_Geruzet_Buildwise.csv")

# Verify files exist
if not os.path.exists(lastenboek_path):
    print(f"Lastenboek file not found: {lastenboek_path}")
    exit(1)
if not os.path.exists(meetstaat_path):
    print(f"Meetstaat file not found: {meetstaat_path}")
    exit(1)

print(f"Files found: {lastenboek_path}, {meetstaat_path}")

# Test standard TOC type
print("\nTesting standard TOC type...")
files = {
    'lastenboek': ('CoordinatedArchitectlastenboek.pdf', open(lastenboek_path, 'rb'), 'application/pdf'),
    'meetstaat': ('meetstaat_Geruzet_Buildwise.csv', open(meetstaat_path, 'rb'), 'text/csv')
}
data = {'toc_type': 'standard'}

try:
    response = requests.post(f"{base_url}/analyze", files=files, data=data)
    print(f"Status code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"TOC type: {result.get('toc_type')}")
        print(f"TOC path: {result.get('toc_path')}")
        print(f"Analysis summary: {result.get('analysis_summary')}")
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Standard TOC request failed: {e}")

# Test vision TOC type
print("\nTesting vision TOC type...")
files = {
    'lastenboek': ('CoordinatedArchitectlastenboek.pdf', open(lastenboek_path, 'rb'), 'application/pdf'),
    'meetstaat': ('meetstaat_Geruzet_Buildwise.csv', open(meetstaat_path, 'rb'), 'text/csv')
}
data = {'toc_type': 'vision'}

try:
    response = requests.post(f"{base_url}/analyze", files=files, data=data)
    print(f"Status code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"TOC type: {result.get('toc_type')}")
        print(f"TOC path: {result.get('toc_path')}")
        print(f"Analysis summary: {result.get('analysis_summary')}")
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Vision TOC request failed: {e}")

print("\nTest completed.") 