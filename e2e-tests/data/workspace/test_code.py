# Test Python code for E2E tests

def add(a, b):
    """Add two numbers"""
    return a + b

def multiply(a, b):
    """Multiply two numbers"""
    return a * b

class Calculator:
    """Simple calculator class"""
    
    def __init__(self):
        self.result = 0
    
    def add_to_result(self, value):
        self.result += value
        return self.result
