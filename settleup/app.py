"""
SettleUp — Group Debt Simplification
--------------------------------------
Problem: In a group trip, people pay for shared expenses unevenly.
Naively, everyone would need to reconcile with everyone else, leading
to O(n^2) transactions. This app computes net balances and applies a
greedy min-cash-flow algorithm to minimize the number of transactions
required to settle all debts within the group.

Data is stored in-memory (per server process) for simplicity — no DB
needed for this demo. Each "trip" is a session of people + expenses.
"""

import heapq
import itertools
import os
import sys
import uuid
from flask import Flask, render_template, request, jsonify, session

# Resolve template/static folders relative to THIS file's location, not thez
# current working directory. This makes `python3 app.py` work correctly
# regardless of where you run it from, as long as templates/ and static/
# are sitting next to app.py on disk.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Fail fast with a clear message instead of a buried Jinja2 traceback if the
# folder structure got separated (e.g. only app.py was downloaded/copied).
if not os.path.isdir(TEMPLATE_DIR):
    sys.exit(
        f"\nERROR: Could not find the 'templates' folder next to app.py.\n"
        f"Expected it at: {TEMPLATE_DIR}\n\n"
        f"Make sure your project folder looks like this:\n"
        f"  settleup/\n"
        f"    app.py\n"
        f"    templates/\n"
        f"      index.html\n"
        f"    static/\n"
        f"      style.css\n"
        f"      app.js\n\n"
        f"If you downloaded files individually, re-download the whole\n"
        f"'settleup' folder (or all 5 files) and keep this layout intact.\n"
    )

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
app.secret_key = "settleup-dev-secret-key-change-in-production"

# In-memory store: trip_id -> {people: [...], expenses: [...]}
TRIPS = {}


def new_trip():
    trip_id = str(uuid.uuid4())[:8]
    TRIPS[trip_id] = {"people": [], "expenses": []}
    return trip_id


def compute_balances(trip):
    """
    Returns dict: person -> net balance.
    Positive balance = is owed money (paid more than their share).
    Negative balance = owes money (consumed more than they paid).
    """
    balances = {p: 0.0 for p in trip["people"]}

    for exp in trip["expenses"]:
        payer = exp["payer"]
        amount = exp["amount"]
        participants = exp["participants"]
        if not participants:
            continue
        share = amount / len(participants)

        balances[payer] = balances.get(payer, 0.0) + amount
        for person in participants:
            balances[person] = balances.get(person, 0.0) - share

    # Round to avoid floating point dust
    return {k: round(v, 2) for k, v in balances.items()}


def minimize_transactions(balances):
    """
    Greedy min-cash-flow settlement algorithm.

    Uses two heaps: one for creditors (owed money, max-heap by amount)
    and one for debtors (owe money, max-heap by amount). At each step,
    match the largest creditor with the largest debtor, settle as much
    as possible, and push back any remainder. This greedy approach
    minimizes the number of transactions in the vast majority of
    real-world cases (it is optimal when balances can be partitioned
    such that greedy matching does not fragment a settlement — the
    theoretically optimal minimum-transaction problem is NP-hard in
    general, but this heuristic performs excellently in practice and
    is what most bill-splitting tools use under the hood).
    """
    creditors = []  # max-heap: (-amount, person)
    debtors = []    # max-heap: (-amount, person)

    EPS = 0.01

    for person, bal in balances.items():
        if bal > EPS:
            heapq.heappush(creditors, (-bal, person))
        elif bal < -EPS:
            heapq.heappush(debtors, (bal, person))  # bal is negative

    transactions = []

    while creditors and debtors:
        neg_credit, creditor = heapq.heappop(creditors)
        neg_debit, debtor = heapq.heappop(debtors)
        credit_amt = -neg_credit
        debit_amt = -neg_debit  # positive number, amount owed

        settle_amt = round(min(credit_amt, debit_amt), 2)
        if settle_amt > EPS:
            transactions.append({
                "from": debtor,
                "to": creditor,
                "amount": settle_amt
            })

        remaining_credit = round(credit_amt - settle_amt, 2)
        remaining_debit = round(debit_amt - settle_amt, 2)

        if remaining_credit > EPS:
            heapq.heappush(creditors, (-remaining_credit, creditor))
        if remaining_debit > EPS:
            heapq.heappush(debtors, (-remaining_debit, debtor))

    return transactions


def naive_transaction_count(trip):
    """How many transactions a naive 'everyone settles with everyone
    they owe individually' approach would take, for comparison."""
    pairs = set()
    for exp in trip["expenses"]:
        payer = exp["payer"]
        for p in exp["participants"]:
            if p != payer:
                pairs.add((p, payer))
    return len(pairs)


@app.route("/")
def index():
    if "trip_id" not in session or session["trip_id"] not in TRIPS:
        session["trip_id"] = new_trip()
    trip = TRIPS[session["trip_id"]]
    return render_template("index.html", trip=trip)


@app.route("/api/person", methods=["POST"])
def add_person():
    trip = TRIPS.get(session.get("trip_id"))
    if trip is None:
        return jsonify({"error": "No active trip"}), 400

    name = request.json.get("name", "").strip()
    if not name:
        return jsonify({"error": "Name cannot be empty"}), 400
    if name in trip["people"]:
        return jsonify({"error": "Person already added"}), 400

    trip["people"].append(name)
    return jsonify({"people": trip["people"]})


@app.route("/api/person/<name>", methods=["DELETE"])
def remove_person(name):
    trip = TRIPS.get(session.get("trip_id"))
    if trip is None:
        return jsonify({"error": "No active trip"}), 400

    if name in trip["people"]:
        trip["people"].remove(name)
        # Also strip them from any expenses
        trip["expenses"] = [
            e for e in trip["expenses"]
            if e["payer"] != name
        ]
        for e in trip["expenses"]:
            if name in e["participants"]:
                e["participants"].remove(name)

    return jsonify({"people": trip["people"]})


@app.route("/api/expense", methods=["POST"])
def add_expense():
    trip = TRIPS.get(session.get("trip_id"))
    if trip is None:
        return jsonify({"error": "No active trip"}), 400

    data = request.json
    description = data.get("description", "").strip() or "Expense"
    payer = data.get("payer")
    participants = data.get("participants", [])
    try:
        amount = float(data.get("amount"))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid amount"}), 400

    if amount <= 0:
        return jsonify({"error": "Amount must be positive"}), 400
    if payer not in trip["people"]:
        return jsonify({"error": "Payer must be a group member"}), 400
    if not participants:
        return jsonify({"error": "Select at least one participant"}), 400
    for p in participants:
        if p not in trip["people"]:
            return jsonify({"error": f"Unknown participant: {p}"}), 400

    trip["expenses"].append({
        "id": str(uuid.uuid4())[:8],
        "description": description,
        "payer": payer,
        "amount": round(amount, 2),
        "participants": participants,
    })

    return jsonify({"expenses": trip["expenses"]})


@app.route("/api/expense/<expense_id>", methods=["DELETE"])
def remove_expense(expense_id):
    trip = TRIPS.get(session.get("trip_id"))
    if trip is None:
        return jsonify({"error": "No active trip"}), 400

    trip["expenses"] = [e for e in trip["expenses"] if e["id"] != expense_id]
    return jsonify({"expenses": trip["expenses"]})


@app.route("/api/settle", methods=["GET"])
def settle():
    trip = TRIPS.get(session.get("trip_id"))
    if trip is None:
        return jsonify({"error": "No active trip"}), 400

    balances = compute_balances(trip)
    transactions = minimize_transactions(dict(balances))
    naive_count = naive_transaction_count(trip)

    return jsonify({
        "balances": balances,
        "transactions": transactions,
        "optimized_count": len(transactions),
        "naive_count": naive_count,
        "transactions_saved": max(0, naive_count - len(transactions)),
    })


@app.route("/api/reset", methods=["POST"])
def reset_trip():
    session["trip_id"] = new_trip()
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)