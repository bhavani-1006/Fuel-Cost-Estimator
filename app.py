import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-this-secret-key")
# Works immediately with SQLite. Set DATABASE_URL to your MySQL URL when ready.
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL", "sqlite:///fuel_estimator.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


class Trip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    start_location = db.Column(db.String(120), nullable=False)
    destination = db.Column(db.String(120), nullable=False)
    distance_km = db.Column(db.Float, nullable=False)
    mileage_kmpl = db.Column(db.Float, nullable=False)
    fuel_price = db.Column(db.Float, nullable=False)
    fuel_type = db.Column(db.String(30), nullable=False, default="Petrol")
    round_trip = db.Column(db.Boolean, nullable=False, default=False)
    fuel_needed = db.Column(db.Float, nullable=False)
    estimated_cost = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def calculate_trip(distance, mileage, price, round_trip=False):
    total_distance = distance * (2 if round_trip else 1)
    fuel_needed = total_distance / mileage
    cost = fuel_needed * price
    return total_distance, fuel_needed, cost


def make_recommendations(distance, mileage, price, cost, fuel_type):
    tips = [
        "Keep tyres properly inflated and maintain the vehicle regularly.",
        "Accelerate smoothly and avoid unnecessary idling to reduce fuel use.",
        "Combine errands where practical to avoid multiple short trips."
    ]
    if mileage < 12:
        tips.insert(0, "Your entered mileage is relatively low; verify it against your vehicle's real-world mileage.")
    if distance >= 300:
        tips.append("For a long journey, compare safe route options and plan rest stops before leaving.")
    return tips


@app.route("/")
def index():
    recent = Trip.query.order_by(Trip.created_at.desc()).limit(5).all()
    totals = {
        "trips": Trip.query.count(),
        "distance": round(sum(t.distance_km * (2 if t.round_trip else 1) for t in Trip.query.all()), 1),
        "cost": round(sum(t.estimated_cost for t in Trip.query.all()), 2),
    }
    return render_template("index.html", recent=recent, totals=totals)


@app.post("/api/calculate")
def api_calculate():
    data = request.get_json(silent=True) or request.form
    try:
        start = str(data.get("start_location", "My location")).strip() or "My location"
        destination = str(data.get("destination", "Destination")).strip() or "Destination"
        distance = float(data.get("distance_km", 0))
        mileage = float(data.get("mileage_kmpl", 0))
        price = float(data.get("fuel_price", 0))
        fuel_type = str(data.get("fuel_type", "Petrol"))
        round_trip = str(data.get("round_trip", "false")).lower() in ("true", "1", "on", "yes")
        if distance <= 0 or mileage <= 0 or price <= 0:
            return jsonify(error="Distance, mileage, and fuel price must all be greater than zero."), 400
        if distance > 100000 or mileage > 200 or price > 10000:
            return jsonify(error="Please check the values entered; one value is unusually large."), 400
    except (TypeError, ValueError):
        return jsonify(error="Enter valid numbers for distance, mileage, and fuel price."), 400

    total_distance, fuel_needed, cost = calculate_trip(distance, mileage, price, round_trip)
    trip = Trip(start_location=start, destination=destination, distance_km=distance,
                mileage_kmpl=mileage, fuel_price=price, fuel_type=fuel_type,
                round_trip=round_trip, fuel_needed=fuel_needed, estimated_cost=cost)
    db.session.add(trip)
    db.session.commit()
    tips = make_recommendations(total_distance, mileage, price, cost, fuel_type)
    return jsonify({
        "id": trip.id, "start_location": start, "destination": destination,
        "distance_km": round(total_distance, 2), "mileage_kmpl": mileage,
        "fuel_price": price, "fuel_type": fuel_type,
        "fuel_needed": round(fuel_needed, 2), "estimated_cost": round(cost, 2),
        "cost_per_km": round(cost / total_distance, 2), "tips": tips
    })


@app.route("/history")
def history():
    trips = Trip.query.order_by(Trip.created_at.desc()).all()
    return render_template("history.html", trips=trips)


@app.post("/history/<int:trip_id>/delete")
def delete_trip(trip_id):
    trip = db.get_or_404(Trip, trip_id)
    db.session.delete(trip)
    db.session.commit()
    flash("Trip deleted.", "success")
    return redirect(url_for("history"))


@app.route("/api/analytics")
def analytics():
    trips = Trip.query.order_by(Trip.created_at.asc()).all()
    return jsonify({
        "labels": [t.created_at.strftime("%d %b %H:%M") for t in trips],
        "costs": [round(t.estimated_cost, 2) for t in trips],
        "distances": [round(t.distance_km * (2 if t.round_trip else 1), 2) for t in trips],
        "fuel": [round(t.fuel_needed, 2) for t in trips],
        "fuel_types": {kind: sum(t.estimated_cost for t in trips if t.fuel_type == kind)
                       for kind in sorted(set(t.fuel_type for t in trips))}
    })


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
