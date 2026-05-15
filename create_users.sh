#!/bin/bash
# Creates test users via auth-service API
set -e

BASE_URL="http://localhost:8000"
echo "=== Creating test users ==="

echo ""
echo "1. Registering admin user..."
curl -sf -X POST "$BASE_URL/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","email":"admin@cinema.local","password":"111111"}' \
  | python3 -m json.tool 2>/dev/null || echo "  (already exists or error)"

echo ""
echo "2. Registering regular user..."
curl -sf -X POST "$BASE_URL/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"user","email":"user@cinema.local","password":"111111"}' \
  | python3 -m json.tool 2>/dev/null || echo "  (already exists or error)"

echo ""
echo "3. Login as admin to get token..."
ADMIN_TOKEN=$(curl -sf -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@cinema.local","password":"111111"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)

if [ -n "$ADMIN_TOKEN" ]; then
  echo "  admin token: ${ADMIN_TOKEN:0:40}..."
else
  echo "  ERROR: could not get admin token"
fi

echo ""
echo "4. Login as user to get token..."
USER_TOKEN=$(curl -sf -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"user@cinema.local","password":"111111"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)

if [ -n "$USER_TOKEN" ]; then
  echo "  user token: ${USER_TOKEN:0:40}..."
else
  echo "  ERROR: could not get user token"
fi

echo ""
echo "5. Getting admin user ID..."
ADMIN_ID=$(curl -sf "$BASE_URL/api/v1/users/me" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
echo "  admin id: $ADMIN_ID"

echo ""
echo "6. Getting user user ID..."
USER_ID=$(curl -sf "$BASE_URL/api/v1/users/me" \
  -H "Authorization: Bearer $USER_TOKEN" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
echo "  user id: $USER_ID"

echo ""
echo "7. Adding sample films to catalog..."
FILM1=$(curl -sf -X POST "$BASE_URL/api/v1/films" \
  -H "Content-Type: application/json" \
  -d '{"title":"Inception","description":"A thief who steals corporate secrets through dream-sharing technology.","rating":8.8,"type":"movie"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
echo "  Film 1 (Inception): $FILM1"

FILM2=$(curl -sf -X POST "$BASE_URL/api/v1/films" \
  -H "Content-Type: application/json" \
  -d '{"title":"The Matrix","description":"A computer hacker learns about the true nature of his reality.","rating":8.7,"type":"movie"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
echo "  Film 2 (The Matrix): $FILM2"

FILM3=$(curl -sf -X POST "$BASE_URL/api/v1/films" \
  -H "Content-Type: application/json" \
  -d '{"title":"Interstellar","description":"A team of explorers travel through a wormhole in space.","rating":8.6,"type":"movie"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
echo "  Film 3 (Interstellar): $FILM3"

echo ""
echo "8. admin adds Inception + Matrix to watchlist..."
curl -sf -X POST "$BASE_URL/api/v1/watchlist" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d "{\"film_work_id\":\"$FILM1\"}" > /dev/null && echo "  admin → Inception ✓"
curl -sf -X POST "$BASE_URL/api/v1/watchlist" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d "{\"film_work_id\":\"$FILM2\"}" > /dev/null && echo "  admin → Matrix ✓"

echo ""
echo "9. user adds Inception + Interstellar to watchlist..."
curl -sf -X POST "$BASE_URL/api/v1/watchlist" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $USER_TOKEN" \
  -d "{\"film_work_id\":\"$FILM1\"}" > /dev/null && echo "  user → Inception ✓"
curl -sf -X POST "$BASE_URL/api/v1/watchlist" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $USER_TOKEN" \
  -d "{\"film_work_id\":\"$FILM3\"}" > /dev/null && echo "  user → Interstellar ✓"

echo ""
echo "10. admin sends friend request to user..."
FRIENDSHIP=$(curl -sf -X POST "$BASE_URL/api/v1/users/friends/request" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d "{\"addressee_id\":\"$USER_ID\"}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['id'])" 2>/dev/null)
echo "  friendship id: $FRIENDSHIP"

echo ""
echo "11. user accepts friend request..."
curl -sf -X PATCH "$BASE_URL/api/v1/users/friends/$FRIENDSHIP/accept" \
  -H "Authorization: Bearer $USER_TOKEN" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  status: {d[\"status\"]}')" 2>/dev/null

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Credentials:"
echo "  admin: email=admin@cinema.local  password=111111"
echo "  user:  email=user@cinema.local   password=111111"
echo ""
echo "Quick test:"
echo "  Matches (admin should see Inception matched with user):"
curl -sf "$BASE_URL/api/v1/matches" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  | python3 -m json.tool 2>/dev/null
