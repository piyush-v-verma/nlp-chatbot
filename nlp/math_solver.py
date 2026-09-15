import re
import sympy
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application

def solve_math(text):
    """
    Solves basic math expressions and equations using SymPy.
    Supports arithmetic, equation solving, derivatives, integrals, and algebraic simplifications.
    """
    if not text or not text.strip():
        return {"error": "Please provide a mathematical expression or equation to solve."}
        
    text_clean = text.strip()
    text_lower = text_clean.lower()
    
    try:
        # Implicit multiplication allows parsing '2x' instead of requiring '2*x'
        transformations = (standard_transformations + (implicit_multiplication_application,))
        
        # 1. Parse Calculus operations
        is_diff = any(kw in text_lower for kw in ["derivative", "differentiate", "diff"])
        is_int = any(kw in text_lower for kw in ["integrate", "integration", "integral"])
        is_simplify = any(kw in text_lower for kw in ["simplify", "factor", "expand"])
        
        # Strip command words to extract the raw math expression
        expr_str = text_clean
        command_verbs = [
            "derivative of", "derivative", "differentiate", "diff", 
            "integrate of", "integrate", "integration", "integral",
            "simplify", "factor", "expand", "solve the equation", "solve equation", "solve"
        ]
        for verb in command_verbs:
            expr_str = re.sub(r'\b' + re.escape(verb) + r'\b', '', expr_str, flags=re.IGNORECASE).strip()
            
        # If there's a colon, the math expression is likely after it (e.g. "equation: 2x + 5 = 15")
        if ":" in expr_str:
            expr_str = expr_str.split(":", 1)[1].strip()
            
        expr_str = expr_str.replace("^", "**") # Convert power symbol to Python power operator
        
        # 2. Check if equation contains an equality symbol '='
        if "=" in expr_str:
            lhs_str, rhs_str = expr_str.split("=", 1)
            lhs = parse_expr(lhs_str.strip(), transformations=transformations)
            rhs = parse_expr(rhs_str.strip(), transformations=transformations)
            eq = sympy.Eq(lhs, rhs)
            
            # Find active symbols
            free_syms = eq.free_symbols
            if not free_syms:
                # Constant equation, check boolean outcome
                res = sympy.simplify(lhs - rhs) == 0
                return {
                    "type": "equation",
                    "operation": "Equality Evaluation",
                    "expression": f"{lhs} = {rhs}",
                    "result": "True" if res else "False",
                    "steps": f"Evaluated equality statement: {lhs} = {rhs} is {res}"
                }
                
            # Solve for first variable found
            var = list(free_syms)[0]
            solution = sympy.solve(eq, var)
            return {
                "type": "equation",
                "operation": "Equation Solving",
                "expression": f"{lhs} = {rhs}",
                "result": str(solution),
                "steps": f"Solved equation for {var}: {var} = {solution}"
            }
            
        # 3. Standard expression parsing (calculus/simplification)
        expr = parse_expr(expr_str, transformations=transformations)
        free_syms = expr.free_symbols
        var = list(free_syms)[0] if free_syms else sympy.Symbol('x')
        
        if is_diff:
            result = sympy.diff(expr, var)
            operation = "Derivative"
            steps = f"d/d{var} ({expr}) = {result}"
        elif is_int:
            result = sympy.integrate(expr, var)
            operation = "Integral"
            steps = f"\u222b ({expr}) d{var} = {result} + C"
        elif is_simplify:
            result = sympy.simplify(expr)
            operation = "Expression Simplification"
            steps = f"Simplified form: {result}"
        else:
            # Direct numeric evaluation if no variables, otherwise algebraic simplification
            if not free_syms:
                result = expr.evalf()
                # Cast to clean integers if possible
                try:
                    if float(result).is_integer():
                        result = int(result)
                    else:
                        result = round(float(result), 4)
                except Exception:
                    pass
                operation = "Arithmetic Evaluation"
                steps = f"Calculated: {expr} = {result}"
            else:
                result = sympy.simplify(expr)
                operation = "Algebraic Simplify"
                steps = f"Evaluated algebraic expression: {result}"
                
        return {
            "type": "calculus" if (is_diff or is_int) else "arithmetic",
            "operation": operation,
            "expression": str(expr),
            "result": str(result),
            "steps": steps
        }
        
    except Exception as e:
        print(f"Sympy Solver error: {e}")
        return {"error": f"Could not solve expression. Details: {str(e)}"}
