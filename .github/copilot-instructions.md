# Copilot Instructions for 3SixtyRev

This project uses the 3SixtyRev SDK with strict code quality guards. Follow these rules.

## 🚫 NEVER Generate These (Will Block Commit)

### Security Violations
```python
# ❌ NEVER hardcode credentials
password = "secret123"           # BLOCKED
api_key = "sk-1234567890"        # BLOCKED
secret = "mysecret"              # BLOCKED

# ✅ ALWAYS use environment variables
password = os.environ.get("DB_PASSWORD")
api_key = os.environ.get("API_KEY")
```

```python
# ❌ NEVER use eval
result = eval(user_input)        # BLOCKED

# ✅ Use safe alternatives
result = json.loads(user_input)
```

```python
# ❌ NEVER use f-strings in SQL
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")  # BLOCKED

# ✅ Use parameterized queries
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
```

### Bandaid Patterns
```python
# ❌ NEVER use these
x = "hello"  # type: ignore     # BLOCKED
import *  # noqa                 # BLOCKED
except: pass                     # BLOCKED
except Exception: pass           # BLOCKED

# ✅ Fix the actual problem or handle properly
try:
    foo()
except ValueError as e:
    logger.error("Error: %s", e)
    raise
```

### Placeholder Code
```python
# ❌ NEVER leave placeholders
def process(): pass  # TODO       # BLOCKED
raise NotImplementedError()       # BLOCKED (except in @abstractmethod)

# ✅ Implement fully or use abstract
@abstractmethod
def process(self): 
    """Subclass must implement."""
    pass
```

### Print Statements
```python
# ❌ AVOID print in production
print("debug")                    # WARNING

# ✅ Use logging
logger.debug("debug message")
```

## ✅ ALWAYS Include

### Type Hints
```python
def get_user(user_id: int) -> Optional[User]:
    return db.query(User).get(user_id)
```

### Docstrings
```python
def calculate_premium(age: int, coverage: float) -> float:
    """Calculate insurance premium.
    
    Args:
        age: Customer's age
        coverage: Coverage amount
        
    Returns:
        Calculated premium
    """
    return base_rate * age_factor(age) * coverage
```

### Proper Error Handling
```python
try:
    result = api.fetch_data()
except requests.RequestException as e:
    logger.error("API failed: %s", e)
    raise DataFetchError(f"Failed: {e}") from e
```

## Project Patterns

### FastAPI Endpoints
```python
@router.post("/bookings", response_model=BookingResponse)
async def create_booking(
    request: BookingRequest,
    db: AsyncSession = Depends(get_db),
) -> BookingResponse:
    """Create a new booking."""
    booking = await BookingService(db).create(request)
    return BookingResponse.model_validate(booking)
```

### Pydantic Models
```python
class BookingRequest(BaseModel):
    customer_name: str = Field(..., min_length=1)
    date: datetime
    service_type: ServiceType
```

### Tests
```python
# ✅ Meaningful assertions
def test_premium_calculation():
    premium = calculate_premium(25, 100000)
    assert premium > 0
    assert premium < 10000

# ❌ NEVER trivial assertions
def test_something():
    assert True  # BLOCKED
```

---
**15 guards check all code before commit. Follow these patterns.**
