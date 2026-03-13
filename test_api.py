"""Quick API endpoint test script."""

import asyncio
from backend.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_all_endpoints():
    """Test all API endpoints."""
    print("Testing Football Elo Rating API endpoints...\n")

    # 1. Health check
    print("1. GET /api/health")
    response = client.get("/api/health")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}\n")

    # 2. Current rankings
    print("2. GET /api/rankings (current, limit=10)")
    response = client.get("/api/rankings?limit=10")
    print(f"   Status: {response.status_code}")
    data = response.json()
    print(f"   Count: {data['count']}")
    print(f"   Top 3: {data['rankings'][:3]}\n")

    # 3. Historical rankings
    print("3. GET /api/rankings?date=2024-01-01")
    response = client.get("/api/rankings?date=2024-01-01&limit=5")
    print(f"   Status: {response.status_code}")
    data = response.json()
    print(f"   Count: {data['count']}")
    print(f"   Date: {data['date']}\n")

    # 4. Search teams
    print("4. GET /api/search?q=arsenal")
    response = client.get("/api/search?q=arsenal")
    print(f"   Status: {response.status_code}")
    data = response.json()
    print(f"   Results: {data['count']}")
    if data['results']:
        team = data['results'][0]
        print(f"   First result: {team}\n")
        team_id = team['id']

        # 5. Team detail
        print(f"5. GET /api/teams/{team_id}")
        response = client.get(f"/api/teams/{team_id}")
        print(f"   Status: {response.status_code}")
        team_detail = response.json()
        print(f"   Name: {team_detail['name']}")
        print(f"   Rating: {team_detail['current_rating']}")
        print(f"   Rank: {team_detail['rank']}")
        print(f"   Recent matches: {len(team_detail['recent_matches'])}\n")

        # 6. Team history
        print(f"6. GET /api/teams/{team_id}/history")
        response = client.get(f"/api/teams/{team_id}/history?limit=10")
        print(f"   Status: {response.status_code}")
        history = response.json()
        print(f"   History points: {len(history['history'])}\n")

    # 7. Search another team for prediction
    print("7. GET /api/search?q=chelsea")
    response = client.get("/api/search?q=chelsea")
    data = response.json()
    if data['results'] and len(data['results']) > 0:
        away_team_id = data['results'][0]['id']

        # 8. Prediction
        print(f"8. GET /api/predict?home={team_id}&away={away_team_id}")
        response = client.get(f"/api/predict?home={team_id}&away={away_team_id}")
        print(f"   Status: {response.status_code}")
        pred = response.json()
        print(f"   {pred['home_team']} vs {pred['away_team']}")
        print(f"   Home win: {pred['p_home']:.2%}")
        print(f"   Draw: {pred['p_draw']:.2%}")
        print(f"   Away win: {pred['p_away']:.2%}\n")

    # 9. Leagues
    print("9. GET /api/leagues")
    response = client.get("/api/leagues")
    print(f"   Status: {response.status_code}")
    data = response.json()
    print(f"   Leagues: {data['count']}")
    print(f"   First 3: {data['leagues'][:3]}\n")

    print("✅ All endpoints tested successfully!")

if __name__ == "__main__":
    test_all_endpoints()
