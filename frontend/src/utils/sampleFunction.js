/**
 * sampleFunction.js — Example Python function for onboarding.
 * Used by WelcomeState to populate the editor for first-time users.
 */

export const SAMPLE_SOURCE_CODE = `def calculate_discount(price: float, discount_percent: float) -> float:
    """Calculate the discounted price.

    Args:
        price: Original price (must be positive).
        discount_percent: Discount percentage (0-100).

    Returns:
        The price after applying the discount.

    Raises:
        ValueError: If price is negative or discount is out of range.
    """
    if price < 0:
        raise ValueError("Price cannot be negative")
    if not 0 <= discount_percent <= 100:
        raise ValueError("Discount must be between 0 and 100")
    return round(price * (1 - discount_percent / 100), 2)`

export const SAMPLE_SPECIFICATION = `Calculate the final price after applying a percentage discount.
Handle edge cases for zero price, full discount, and invalid inputs.`

export const SAMPLE_LANGUAGE = 'python'
export const SAMPLE_FRAMEWORK = 'pytest'
