# SettleUp — Group Debt Simplification

> A lightweight Flask application designed to solve a common problem: minimizing the number of transactions needed to settle shared group expenses.

---

## 💡 The Problem

When a group splits costs unevenly across a trip (one person books the hotel, another covers dinner, a third pays for the taxi—and the group sizes differ each time), the typical fix is for everyone to reconcile pairwise. 

This results in $O(n^2)$ transactions in the worst case, most of which are redundant. For example, if Alice owes Bob $10 and Bob owes Carol $10, Bob doesn't need to touch the money at all.

### How SettleUp Solves It
1. Computes each person's **net balance** (what they paid minus their fair share across all expenses).
2. Runs a **greedy min-cash-flow algorithm** (matching the largest creditor against the largest debtor repeatedly) to collapse the tangle into the smallest practical set of "who pays whom" transactions.

---

## 🚀 Quick Start

### Prerequisites
Make sure you have Python 3 and `pip` installed.

### Installation & Running
```bash
# Clone the repository (or navigate to the project directory)
cd settleup

# Install dependencies
pip install flask

# Run the application
python3 app.py


🕹️ Working:
1. Add People: Add all participants to the trip.
2. Log Expenses: Record who paid, how much, and who the cost is split between (splits don't have to include everyone every time).
3. View the Ledger: The Ledger panel shows each person's net position in real-time (green means they are owed money; red means they owe).
4. Settle Up: The Settlement panel calculates the minimum set of transactions required to zero everyone out, highlighting how many fewer transactions are needed compared to the naive pairwise approach.


📂 Project Structure:
.
├── app.py                  # Flask routes + balance/settlement algorithm
├── templates/
│   └── index.html          # Main HTML interface
└── static/
    ├── style.css           # Minimalist styling (monochrome + two accent colors)
    └── app.js              # Frontend logic (fetch-based, vanilla JS)


🛠️ Technical Details:
Backend: Python / Flask
Frontend: Vanilla JavaScript (Fetch API), HTML5, CSS3
State Management: In-memory per session using a trip_id cookie (self-contained demo requiring no database). Note that restarting the server clears all active trips.
