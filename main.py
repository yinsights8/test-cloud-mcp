from fastmcp import FastMCP
import aiosqlite
import sqlite3
import os

# how to run
# Step 1: terminal 1: uv run main.py  
# Step 2: terminal 2: npx @modelcontextprotocol/inspector
# Step 3: paste this localhost url and /mcp i.e 
#         http://0.0.0.0:8000/mcp in url field


DB_PATH = "src"
DB_NAME = "personal_expence_tracker.db"
CATEGORIES = "categories.json"  # required

if not os.path.exists(DB_PATH):
    os.makedirs(DB_PATH, exist_ok=True)

DB_FILE_PATH = os.path.join(DB_PATH, DB_NAME)
CATEGORIES_PATH = os.path.join(DB_PATH, CATEGORIES)  # manually create categories to present auto selection by llm

mcp = FastMCP("ExpenseTracker", host="0.0.0.0", port=8000)


def init_db():
    
    try:
        with sqlite3.connect(DB_FILE_PATH) as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("""
                CREATE TABLE IF NOT EXISTS expenses(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    amount REAL NOT NULL,
                    category TEXT NOT NULL,
                    subcategory TEXT DEFAULT '',
                    note TEXT DEFAULT ''
                )
            """)
            
            c.execute("""
                CREATE TABLE IF NOT EXISTS credits(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    amount REAL NOT NULL,
                    category TEXT NOT NULL,
                    subcategory TEXT DEFAULT '',
                    note TEXT DEFAULT ''
                )
            """)
            
            c.execute("INSERT OR IGNORE INTO expenses(date, amount, category) VALUES ('2000-01-01', 0, 'test')")
            c.execute("DELETE FROM expenses WHERE category = 'test'")
            print("Database initialized successfully with write access")
    except Exception as e:
        print(f"Database initialization error: {e}")
        raise

init_db()

@mcp.tool()
async def add_expense(date, amount, category, subcategory="", note=""):
    '''Add a new expense entry to the database.'''
    try:
        async with aiosqlite.connect(DB_FILE_PATH) as c:
            
            cur = await c.execute(
                "INSERT INTO expenses(date, amount, category, subcategory, note) VALUES (?,?,?,?,?)",
                (date, amount, category, subcategory, note)
            )
            expense_id = cur.lastrowid
            await c.commit()  # Explicit commit
            return {"status": "ok", "id": expense_id}
    except sqlite3.OperationalError as e:
        if "read-only" in str(e).lower():
            return {"status": "error", "message": f"Database is read-only: {e}"}
        raise
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
    
@mcp.tool()
async def list_expenses(start_date, end_date):
    '''List expense entries within an inclusive date range.'''
    async with aiosqlite.connect(DB_FILE_PATH) as c:
        cur = await c.execute(
            """
            SELECT id, date, amount, category, subcategory, note
            FROM expenses
            WHERE date BETWEEN ? AND ?
            ORDER BY id ASC
            """,
            (start_date, end_date)
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

@mcp.tool()
async def remove_expenses(date, amount, category, subcategory="", note=""):
    """Delete expenses matching the specified criteria"""
    async with aiosqlite.connect(DB_FILE_PATH) as c:
        cur = await c.execute(
            """
            DELETE FROM expenses 
            WHERE date = ? AND amount = ? AND category = ? AND subcategory = ? AND note = ?
            """,
            (date, amount, category, subcategory, note)
        )
        if cur.rowcount > 0:
            return {"status": "ok", "message": f"Deleted {cur.rowcount} expense(s)"}
        else:
            return {"status": "error", "message": "No matching expenses found"}

@mcp.tool()
async def edit_expenses(expense_id, date, amount, category, subcategory="", note=""):
    """Edit an existing expense. Only provide values for fields you want to update."""
    update_fields = []
    params = []
    
    if date is not None:
        update_fields.append("date = ?")
        params.append(date)
    if amount is not None:
        update_fields.append("amount = ?")
        params.append(amount)
    if category is not None:
        update_fields.append("category = ?")
        params.append(category)
    if subcategory is not None:
        update_fields.append("subcategory = ?")
        params.append(subcategory)
    if note is not None:
        update_fields.append("note = ?")
        params.append(note)
        
    if not update_fields:
        return {"status": "error", "message": "No fields provided to update"}
    # Add the ID to the parameters for the WHERE clause
    params.append(expense_id)
    
    # Build the UPDATE query
    query = f"UPDATE expenses SET {', '.join(update_fields)} WHERE id = ?"
    
    async with aiosqlite.connect(DB_FILE_PATH) as c:
        cur = await c.execute(query, params)
        if cur.rowcount > 0:
            return {"status": "ok", "message": f"Expense {expense_id} updated successfully"}
        else:
            return {"status": "error", "message": f"Expense {expense_id} not found"}

@mcp.tool()
async def summarize(start_date, end_date, category=None):
    '''Summarize expenses by category within an inclusive date range.'''
    async with aiosqlite.connect(DB_FILE_PATH) as c:
        query = (
            """
            SELECT category, SUM(amount) AS total_amount
            FROM expenses
            WHERE date BETWEEN ? AND ?
            """
        )
        params = [start_date, end_date]

        if category:
            query += " AND category = ?"
            params.append(category)

        query += " GROUP BY category ORDER BY category ASC"

        cur = await c.execute(query, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]






@mcp.tool()
async def credit_amount(date, amount, category, subcategory="", note=""):
    """Add a new credit/income entry to the database.
    
    Args:
        date (str): Date in YYYY-MM-DD format
        amount (float): Income amount
        category (str): Income category (employment, investments, etc.)
        subcategory (str, optional): Specific subcategory
        note (str, optional): Additional notes
    """
    try:
        with aiosqlite.connect(DB_FILE_PATH) as c:
            cur = await c.execute(
                """
                INSERT INTO credits (date, amount, category, subcategory, note) 
                VALUES (?, ?, ?, ?, ?)
                """,
                (date, amount, category, subcategory, note)
            )
            return {"status": "ok", "id": cur.lastrowid, "message": f"Credit entry added with ID {cur.lastrowid}"}
    except Exception as e:
        return {"status": "error", "message": f"Database error: {str(e)}"}
    
    
    
@mcp.tool()
async def list_credits(start_date, end_date):
    '''List credits entries within an inclusive date range.'''
    with aiosqlite.connect(DB_FILE_PATH) as c:
        cur = await c.execute(
            """
            SELECT id, date, amount, category, subcategory, note
            FROM credits
            WHERE date BETWEEN ? AND ?
            ORDER BY id ASC
            """,
            (start_date, end_date)
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

@mcp.tool()
async def remove_credits(date, amount, category, subcategory="", note=""):
    """Delete expenses matching the specified criteria"""
    with aiosqlite.connect(DB_FILE_PATH) as c:
        cur = await c.execute(
            """
            DELETE FROM credits 
            WHERE date = ? AND amount = ? AND category = ? AND subcategory = ? AND note = ?
            """,
            (date, amount, category, subcategory, note)
        )
        if cur.rowcount > 0:
            return {"status": "ok", "message": f"Deleted {cur.rowcount} expense(s)"}
        else:
            return {"status": "error", "message": "No matching expenses found"}

@mcp.tool()
async def edit_credits(expense_id, date, amount, category, subcategory="", note=""):
    """Edit an existing expense. Only provide values for fields you want to update."""
    update_fields = []
    params = []
    
    if date is not None:
        update_fields.append("date = ?")
        params.append(date)
    if amount is not None:
        update_fields.append("amount = ?")
        params.append(amount)
    if category is not None:
        update_fields.append("category = ?")
        params.append(category)
    if subcategory is not None:
        update_fields.append("subcategory = ?")
        params.append(subcategory)
    if note is not None:
        update_fields.append("note = ?")
        params.append(note)
        
    if not update_fields:
        return {"status": "error", "message": "No fields provided to update"}
    # Add the ID to the parameters for the WHERE clause
    params.append(expense_id)
    
    # Build the UPDATE query
    query = f"UPDATE credits SET {', '.join(update_fields)} WHERE id = ?"
    
    with aiosqlite.connect(DB_FILE_PATH) as c:
        cur = await c.execute(query, params)
        if cur.rowcount > 0:
            return {"status": "ok", "message": f"credits {expense_id} updated successfully"}
        else:
            return {"status": "error", "message": f"credits {expense_id} not found"}
    
@mcp.tool()
async def summarize_credit(start_date, end_date, category=None):
    '''Summarize expenses by category within an inclusive date range.'''
    with aiosqlite.connect(DB_FILE_PATH) as c:
        query = (
            """
            SELECT category, SUM(amount) AS total_amount
            FROM credits
            WHERE date BETWEEN ? AND ?
            """
        )
        params = [start_date, end_date]

        if category:
            query += " AND category = ?"
            params.append(category)

        query += " GROUP BY category ORDER BY category ASC"

        cur = await c.execute(query, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]



@mcp.resource("expense://categories", mime_type="application/json")
def categories():
    # Read fresh each time so you can edit the file without restarting
    with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
        return f.read()
if __name__ == "__main__":
    mcp.run(transport="streamable-http")
