from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import jwt
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)
@app.route("/")
def home():
    return {
        "message": "SkillSwap API is running",
        "status": "ok"
    }

SECRET = os.getenv("JWT_SECRET", "skillswap-demo-secret-2026")

# Demo database fallback
users = []
skills = []
requests_db = []
reviews = []

def token_for(user):
    return jwt.encode(
        {"user_id": user["id"], "exp": datetime.utcnow() + timedelta(days=2)},
        SECRET,
        algorithm="HS256"
    )

def auth_user():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    try:
        payload = jwt.decode(header[7:], SECRET, algorithms=["HS256"])
        return next((u for u in users if u["id"] == payload["user_id"]), None)
    except:
        return None

def next_id(collection):
    return max([x["id"] for x in collection], default=0) + 1


@app.get("/")
def home():
    return jsonify({
        "name": "SkillSwap API",
        "version": "1.0",
        "status": "online",
        "message": "Student Skill Exchange Platform",
        "endpoints": [
            "/api/health",
            "/api/users",
            "/api/skills",
            "/api/requests",
            "/api/stats"
        ]
    })


@app.get("/api/health")
def health():
    return jsonify({
        "status": "healthy",
        "database": "demo-memory",
        "timestamp": datetime.utcnow().isoformat()
    })


# ---------------- AUTH ----------------

@app.post("/api/auth/register")
def register():
    data = request.json or {}

    required = ["name", "email", "password"]
    if not all(data.get(x) for x in required):
        return jsonify({"error": "Name, email and password are required"}), 400

    if any(u["email"].lower() == data["email"].lower() for u in users):
        return jsonify({"error": "Email already registered"}), 409

    user = {
        "id": next_id(users),
        "name": data["name"],
        "email": data["email"],
        "password": generate_password_hash(data["password"]),
        "bio": data.get("bio", ""),
        "availability": data.get("availability", "Flexible"),
        "skills": data.get("skills", []),
        "role": "student",
        "rating": 0,
        "reviews": 0
    }

    users.append(user)

    return jsonify({
        "message": "Account created",
        "token": token_for(user),
        "user": {k: v for k, v in user.items() if k != "password"}
    }), 201


@app.post("/api/auth/login")
def login():
    data = request.json or {}

    user = next(
        (u for u in users if u["email"].lower() == data.get("email", "").lower()),
        None
    )

    if not user or not check_password_hash(user["password"], data.get("password", "")):
        return jsonify({"error": "Invalid email or password"}), 401

    return jsonify({
        "message": "Login successful",
        "token": token_for(user),
        "user": {k: v for k, v in user.items() if k != "password"}
    })


# ---------------- USERS ----------------

@app.get("/api/users")
def get_users():
    return jsonify([
        {k: v for k, v in u.items() if k != "password"}
        for u in users
    ])


@app.get("/api/users/<int:user_id>")
def get_user(user_id):
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        return jsonify({"error": "User not found"}), 404

    result = {k: v for k, v in user.items() if k != "password"}
    result["teaching"] = [s for s in skills if s["teacher_id"] == user_id]
    return jsonify(result)


@app.put("/api/users/profile")
def update_profile():
    user = auth_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.json or {}

    for field in ["name", "bio", "availability", "skills"]:
        if field in data:
            user[field] = data[field]

    return jsonify({
        "message": "Profile updated",
        "user": {k: v for k, v in user.items() if k != "password"}
    })


# ---------------- SKILLS ----------------

@app.get("/api/skills")
def get_skills():
    keyword = request.args.get("keyword", "").lower()
    category = request.args.get("category", "").lower()

    result = skills

    if keyword:
        result = [
            s for s in result
            if keyword in s["title"].lower()
            or keyword in s["description"].lower()
            or keyword in s["category"].lower()
        ]

    if category and category != "all":
        result = [s for s in result if s["category"].lower() == category]

    enriched = []

    for s in result:
        teacher = next((u for u in users if u["id"] == s["teacher_id"]), None)

        enriched.append({
            **s,
            "teacher": teacher["name"] if teacher else "Student",
            "teacher_rating": teacher["rating"] if teacher else 0
        })

    return jsonify(enriched)


@app.post("/api/skills")
def create_skill():
    user = auth_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.json or {}

    if not data.get("title") or not data.get("category"):
        return jsonify({"error": "Title and category are required"}), 400

    skill = {
        "id": next_id(skills),
        "teacher_id": user["id"],
        "title": data["title"],
        "category": data["category"],
        "description": data.get("description", ""),
        "level": data.get("level", "Beginner"),
        "mode": data.get("mode", "Online"),
        "availability": data.get("availability", user.get("availability", "Flexible")),
        "created_at": datetime.utcnow().isoformat()
    }

    skills.append(skill)

    return jsonify(skill), 201


@app.put("/api/skills/<int:skill_id>")
def update_skill(skill_id):
    user = auth_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    skill = next((s for s in skills if s["id"] == skill_id), None)

    if not skill:
        return jsonify({"error": "Skill not found"}), 404

    if skill["teacher_id"] != user["id"]:
        return jsonify({"error": "Not authorized"}), 403

    data = request.json or {}

    for field in ["title", "category", "description", "level", "mode", "availability"]:
        if field in data:
            skill[field] = data[field]

    return jsonify(skill)


@app.delete("/api/skills/<int:skill_id>")
def delete_skill(skill_id):
    user = auth_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    skill = next((s for s in skills if s["id"] == skill_id), None)

    if not skill:
        return jsonify({"error": "Skill not found"}), 404

    if skill["teacher_id"] != user["id"]:
        return jsonify({"error": "Not authorized"}), 403

    skills.remove(skill)

    return jsonify({"message": "Skill deleted"})


# ---------------- REQUESTS ----------------

@app.post("/api/requests")
def send_request():
    user = auth_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.json or {}

    skill = next(
        (s for s in skills if s["id"] == data.get("skill_id")),
        None
    )

    if not skill:
        return jsonify({"error": "Skill not found"}), 404

    if skill["teacher_id"] == user["id"]:
        return jsonify({"error": "You cannot request your own skill"}), 400

    req = {
        "id": next_id(requests_db),
        "skill_id": skill["id"],
        "learner_id": user["id"],
        "teacher_id": skill["teacher_id"],
        "message": data.get("message", "I would like to learn this skill."),
        "status": "pending",
        "created_at": datetime.utcnow().isoformat()
    }

    requests_db.append(req)

    return jsonify(req), 201


@app.get("/api/requests")
def get_requests():
    user = auth_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    result = [
        r for r in requests_db
        if r["learner_id"] == user["id"] or r["teacher_id"] == user["id"]
    ]

    return jsonify(result)


@app.patch("/api/requests/<int:request_id>")
def update_request(request_id):
    user = auth_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    req = next((r for r in requests_db if r["id"] == request_id), None)

    if not req:
        return jsonify({"error": "Request not found"}), 404

    if req["teacher_id"] != user["id"]:
        return jsonify({"error": "Only the teacher can manage this request"}), 403

    status = (request.json or {}).get("status")

    if status not in ["accepted", "rejected", "completed"]:
        return jsonify({"error": "Invalid status"}), 400

    req["status"] = status
    req["updated_at"] = datetime.utcnow().isoformat()

    return jsonify(req)


# ---------------- REVIEWS ----------------

@app.post("/api/reviews")
def create_review():
    user = auth_user()

    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.json or {}

    rating = int(data.get("rating", 0))

    if rating < 1 or rating > 5:
        return jsonify({"error": "Rating must be between 1 and 5"}), 400

    review = {
        "id": next_id(reviews),
        "reviewer_id": user["id"],
        "teacher_id": data.get("teacher_id"),
        "rating": rating,
        "comment": data.get("comment", ""),
        "created_at": datetime.utcnow().isoformat()
    }

    reviews.append(review)

    teacher = next((u for u in users if u["id"] == review["teacher_id"]), None)

    if teacher:
        teacher_reviews = [
            r for r in reviews if r["teacher_id"] == teacher["id"]
        ]
        teacher["rating"] = round(
            sum(r["rating"] for r in teacher_reviews) / len(teacher_reviews), 1
        )
        teacher["reviews"] = len(teacher_reviews)

    return jsonify(review), 201


# ---------------- DASHBOARD / ANALYTICS ----------------

@app.get("/api/stats")
def stats():
    return jsonify({
        "students": len(users),
        "skills": len(skills),
        "requests": len(requests_db),
        "pending_requests": len([
            r for r in requests_db if r["status"] == "pending"
        ]),
        "completed_exchanges": len([
            r for r in requests_db if r["status"] == "completed"
        ]),
        "reviews": len(reviews),
        "categories": len(set(s["category"] for s in skills))
    })


# ---------------- DEMO DATA ----------------

def seed_demo():
    if users:
        return

    demo_users = [
        ("Aarav", "aarav@skillswap.demo", ["Python", "Flask", "MongoDB"]),
        ("Diya", "diya@skillswap.demo", ["UI/UX", "Figma", "Design"]),
        ("Rahul", "rahul@skillswap.demo", ["React", "JavaScript", "Web Development"]),
        ("Ananya", "ananya@skillswap.demo", ["Photography", "Video Editing"])
    ]

    for name, email, user_skills in demo_users:
        users.append({
            "id": next_id(users),
            "name": name,
            "email": email,
            "password": generate_password_hash("demo123"),
            "bio": f"Student passionate about {user_skills[0]} and peer learning.",
            "availability": "Weekends",
            "skills": user_skills,
            "role": "student",
            "rating": 4.8,
            "reviews": 12
        })

    demo_skills = [
        ("Python Backend Development", "Programming", 1, "Build REST APIs with Python and Flask."),
        ("UI/UX Design with Figma", "Design", 2, "Learn practical interface and prototype design."),
        ("React Web Development", "Programming", 3, "Build modern responsive React applications."),
        ("Photography Basics", "Creative", 4, "Composition, lighting and mobile photography.")
    ]

    for title, category, teacher, description in demo_skills:
        skills.append({
            "id": next_id(skills),
            "teacher_id": teacher,
            "title": title,
            "category": category,
            "description": description,
            "level": "Intermediate",
            "mode": "Online",
            "availability": "Weekends",
            "created_at": datetime.utcnow().isoformat()
        })


seed_demo()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
