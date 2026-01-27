"""
Utility functions for Migros price analysis.
Used by recon.ipynb for price change detection and shrinkflation analysis.
"""

import re
import pandas as pd
import numpy as np


# =============================================================================
# QUANTITY PARSING (for API quality analysis)
# =============================================================================

def parse_quantity_to_unit_price(quantity_str: str, effective_value: float) -> tuple:
    """
    Parse quantity string and calculate price per 100g/100ml.

    Args:
        quantity_str: Product quantity string (e.g., '500g', '1.5l', '6 x 1.5l')
        effective_value: Product price in CHF

    Returns:
        Tuple of (unit_price, unit_type) or (None, None) if can't parse
    """
    if not quantity_str or not effective_value or effective_value <= 0:
        return None, None

    q = quantity_str.strip().lower()

    # Skip non-weight/volume items (pieces, pairs, etc.)
    skip_patterns = ['stk', 'piece', 'paar', 'st.', 'st ', 'sück', 'stück',
                     'per kg', '100 g', '100g', '100ml', '100 ml']
    for skip in skip_patterns:
        if skip in q:
            return None, None

    # Pattern: number + unit (g, kg, ml, l, cl, dl)
    match = re.match(r'^([\d.,]+)\s*(g|kg|ml|l|cl|dl)$', q)
    if not match:
        # Try with 'x' multiplier: '6 x 1.5l'
        match = re.match(r'^(\d+)\s*x\s*([\d.,]+)\s*(g|kg|ml|l|cl|dl)$', q)
        if match:
            multiplier = float(match.group(1))
            amount = float(match.group(2).replace(',', '.'))
            unit = match.group(3)
            amount = amount * multiplier
        else:
            return None, None
    else:
        amount = float(match.group(1).replace(',', '.'))
        unit = match.group(2)

    # Convert to base unit (g or ml)
    if unit == 'kg':
        amount_base = amount * 1000
        base_unit = '100g'
    elif unit == 'g':
        amount_base = amount
        base_unit = '100g'
    elif unit == 'l':
        amount_base = amount * 1000
        base_unit = '100ml'
    elif unit in ('cl', 'dl', 'ml'):
        if unit == 'cl':
            amount_base = amount * 10
        elif unit == 'dl':
            amount_base = amount * 100
        else:
            amount_base = amount
        base_unit = '100ml'
    else:
        return None, None

    if amount_base <= 0:
        return None, None

    # Calculate price per 100g/100ml
    price_per_100 = (effective_value / amount_base) * 100
    return price_per_100, base_unit


# =============================================================================
# QUANTITY PARSING (extract numeric amount)
# =============================================================================

def parse_quantity_amount(quantity_str: str) -> tuple:
    """
    Parse quantity string and extract the total amount in base units.

    Args:
        quantity_str: Product quantity string (e.g., '500g', '1.5l', '6 x 1.5l')

    Returns:
        Tuple of (amount_in_base_unit, unit_type) or (None, None) if can't parse
        unit_type is 'g' for weight or 'ml' for volume
    """
    if not quantity_str:
        return None, None

    q = quantity_str.strip().lower()

    # Skip non-weight/volume items (pieces, pairs, etc.)
    skip_patterns = ['stk', 'piece', 'paar', 'st.', 'stück', 'per kg', '100 g', '100g', '100ml', '100 ml']
    for skip in skip_patterns:
        if skip in q:
            return None, None

    # Pattern: number + unit (g, kg, ml, l, cl, dl)
    match = re.match(r'^([\d.,]+)\s*(g|kg|ml|l|cl|dl)$', q)
    if not match:
        # Try with 'x' multiplier: '6 x 1.5l'
        match = re.match(r'^(\d+)\s*x\s*([\d.,]+)\s*(g|kg|ml|l|cl|dl)$', q)
        if match:
            multiplier = float(match.group(1))
            amount = float(match.group(2).replace(',', '.'))
            unit = match.group(3)
            amount = amount * multiplier
        else:
            return None, None
    else:
        amount = float(match.group(1).replace(',', '.'))
        unit = match.group(2)

    # Convert to base unit (g or ml)
    if unit == 'kg':
        amount_base = amount * 1000
        base_unit = 'g'
    elif unit == 'g':
        amount_base = amount
        base_unit = 'g'
    elif unit == 'l':
        amount_base = amount * 1000
        base_unit = 'ml'
    elif unit in ('cl', 'dl', 'ml'):
        if unit == 'cl':
            amount_base = amount * 10
        elif unit == 'dl':
            amount_base = amount * 100
        else:
            amount_base = amount
        base_unit = 'ml'
    else:
        return None, None

    if amount_base <= 0:
        return None, None

    return amount_base, base_unit


# =============================================================================
# SHRINKFLATION DETECTION (quantity changes)
# =============================================================================

def find_shrinkflation(products: list, max_price_change_pct: float = 5.0) -> pd.DataFrame:
    """
    Detect shrinkflation: cases where quantity changed while price stayed similar.

    Args:
        products: List of MongoDB product documents
        max_price_change_pct: Maximum price change to consider "same price" (default 5%)

    Returns:
        DataFrame with shrinkflation cases
    """
    # Build dataframe with parsed quantities
    data = []
    for p in products:
        offer = p.get('offer', {})
        price_obj = offer.get('price', {})
        effective = price_obj.get('effectiveValue')
        quantity_str = offer.get('quantity', '')

        if not effective or effective <= 0 or not quantity_str:
            continue

        amount, unit_type = parse_quantity_amount(quantity_str)
        if amount is None:
            continue

        data.append({
            'migrosId': p['migrosId'],
            'name': p.get('name', 'Unknown'),
            'effectiveValue': effective,
            'quantity_str': quantity_str,
            'quantity_amount': amount,
            'unit_type': unit_type,
            'dateAdded': p.get('dateAdded')
        })

    df = pd.DataFrame(data)
    if df.empty:
        return pd.DataFrame()

    df['dateAdded'] = pd.to_datetime(df['dateAdded'])
    df = df.sort_values(['migrosId', 'dateAdded'])

    # Find quantity changes
    shrinkflation_cases = []

    for migros_id, group in df.groupby('migrosId'):
        if len(group) <= 1:
            continue

        group = group.sort_values('dateAdded')

        for i in range(1, len(group)):
            old_row = group.iloc[i-1]
            new_row = group.iloc[i]

            # Must be same unit type (both g or both ml)
            if old_row['unit_type'] != new_row['unit_type']:
                continue

            old_qty = old_row['quantity_amount']
            new_qty = new_row['quantity_amount']
            old_price = old_row['effectiveValue']
            new_price = new_row['effectiveValue']

            # Skip if quantity didn't change
            if old_qty == new_qty:
                continue

            # Calculate changes
            qty_change_pct = ((new_qty - old_qty) / old_qty) * 100
            price_change_pct = ((new_price - old_price) / old_price) * 100

            # Calculate unit price change (price per gram/ml)
            old_unit_price = old_price / old_qty
            new_unit_price = new_price / new_qty
            unit_price_change_pct = ((new_unit_price - old_unit_price) / old_unit_price) * 100

            # Shrinkflation: quantity decreased while price stayed similar or increased
            # Also catch reverse: quantity increased while price stayed similar (good for consumer)
            is_shrinkflation = qty_change_pct < -1 and price_change_pct >= -max_price_change_pct
            is_expansion = qty_change_pct > 1 and price_change_pct <= max_price_change_pct

            if is_shrinkflation or is_expansion:
                shrinkflation_cases.append({
                    'migrosId': migros_id,
                    'name': new_row['name'],
                    'old_quantity': old_row['quantity_str'],
                    'new_quantity': new_row['quantity_str'],
                    'old_amount': old_qty,
                    'new_amount': new_qty,
                    'unit_type': new_row['unit_type'],
                    'qty_change_pct': qty_change_pct,
                    'old_price': old_price,
                    'new_price': new_price,
                    'price_change_pct': price_change_pct,
                    'unit_price_change_pct': unit_price_change_pct,
                    'date': new_row['dateAdded'],
                    'type': 'shrinkflation' if is_shrinkflation else 'expansion'
                })

    return pd.DataFrame(shrinkflation_cases)


def print_shrinkflation(df: pd.DataFrame, n: int = 20, shrinkflation: bool = True):
    """Print shrinkflation or expansion cases in a formatted table."""
    if df.empty:
        print("No cases to display.")
        return df

    if shrinkflation:
        filtered = df[df['type'] == 'shrinkflation'].copy()
        if filtered.empty:
            print("No shrinkflation cases found.")
            return filtered
        # Sort by quantity decrease (most shrunk first)
        filtered = filtered.nsmallest(n, 'qty_change_pct')
        title = f"TOP {n} SHRINKFLATION CASES (quantity reduced, price similar)"
    else:
        filtered = df[df['type'] == 'expansion'].copy()
        if filtered.empty:
            print("No expansion cases found.")
            return filtered
        # Sort by quantity increase (most expanded first)
        filtered = filtered.nlargest(n, 'qty_change_pct')
        title = f"TOP {n} EXPANSION CASES (quantity increased, price similar)"

    print(f"\n{title}:")
    print("=" * 130)
    print(f"{'migrosId':<14} {'Product':<25} {'Old Qty':<10} {'New Qty':<10} {'Qty Chg':>8} {'Old CHF':>8} {'New CHF':>8} {'Unit +%':>8} {'Date':<12}")
    print("-" * 130)

    for _, row in filtered.iterrows():
        qty_chg = f"{row['qty_change_pct']:+.1f}%"
        unit_chg = f"{row['unit_price_change_pct']:+.1f}%"
        print(f"{row['migrosId']:<14} {row['name'][:23]:<25} {row['old_quantity'][:8]:<10} {row['new_quantity'][:8]:<10} "
              f"{qty_chg:>8} {row['old_price']:>7.2f} {row['new_price']:>7.2f} {unit_chg:>8} {str(row['date'])[:10]:<12}")

    return filtered


# =============================================================================
# PRICE CHANGE TRACKING (using effective price + same quantity)
# =============================================================================

def build_price_history_df(products: list) -> pd.DataFrame:
    """
    Build a DataFrame for price history tracking.

    Uses effective price directly - no unit price normalization needed.
    Price changes are detected by comparing entries with the same quantity string.

    Args:
        products: List of MongoDB product documents

    Returns:
        DataFrame with columns: migrosId, name, effectiveValue, quantity, dateAdded
    """
    data = []
    skipped = 0

    for p in products:
        offer = p.get('offer', {})
        price_obj = offer.get('price', {})
        effective = price_obj.get('effectiveValue')
        quantity = offer.get('quantity', '')

        if not effective or effective <= 0:
            skipped += 1
            continue

        if not quantity:
            skipped += 1
            continue

        data.append({
            'migrosId': p['migrosId'],
            'name': p.get('name', 'Unknown'),
            'effectiveValue': effective,
            'quantity': quantity,
            'dateAdded': p.get('dateAdded')
        })

    df = pd.DataFrame(data)
    if not df.empty:
        df['dateAdded'] = pd.to_datetime(df['dateAdded'])
        df = df.sort_values(['migrosId', 'dateAdded'])

    print(f"Built price history: {len(df)} entries, {skipped} skipped (no price/quantity)")
    return df


def find_price_changes_v2(df: pd.DataFrame, min_change_pct: float = 1.0) -> pd.DataFrame:
    """
    Find price changes between consecutive observations of the same product.

    Only compares entries where the quantity string is IDENTICAL.
    This ensures we're comparing apples to apples (same package size).

    Args:
        df: DataFrame from build_price_history_df()
        min_change_pct: Minimum percentage change to count (filters noise)

    Returns:
        DataFrame with price changes
    """
    changes = []

    for migros_id, group in df.groupby('migrosId'):
        if len(group) <= 1:
            continue

        group = group.sort_values('dateAdded')

        for i in range(1, len(group)):
            old_row = group.iloc[i-1]
            new_row = group.iloc[i]

            # CRITICAL: Only compare if quantity string is IDENTICAL
            if old_row['quantity'] != new_row['quantity']:
                continue

            old_price = old_row['effectiveValue']
            new_price = new_row['effectiveValue']

            # Skip if prices are the same
            if old_price == new_price:
                continue

            # Only count as change if price differs by > min_change_pct
            if old_price > 0 and abs(new_price - old_price) / old_price > (min_change_pct / 100):
                pct_change = ((new_price - old_price) / old_price) * 100

                changes.append({
                    'migrosId': migros_id,
                    'name': new_row['name'],
                    'quantity': new_row['quantity'],
                    'old_price': old_price,
                    'new_price': new_price,
                    'pct_change': pct_change,
                    'date': new_row['dateAdded']
                })

    return pd.DataFrame(changes)


def filter_price_changes(df: pd.DataFrame,
                         min_price: float = 0.10,
                         max_price: float = 500,
                         max_pct_change: float = 100) -> pd.DataFrame:
    """
    Filter out outliers from price change DataFrame.

    Args:
        df: DataFrame from find_price_changes_v2()
        min_price: Minimum effective price (CHF)
        max_price: Maximum effective price (CHF)
        max_pct_change: Maximum absolute percentage change

    Returns:
        Filtered DataFrame
    """
    if df.empty:
        return df
    return df[
        (df['old_price'] >= min_price) &
        (df['old_price'] <= max_price) &
        (df['pct_change'].abs() <= max_pct_change)
    ].copy()


def print_price_changes(df: pd.DataFrame, n: int = 20, increases: bool = True):
    """Print top price changes in a formatted table."""
    if df.empty:
        print("No price changes to display.")
        return df

    if increases:
        top = df[df['pct_change'] > 0].nlargest(n, 'pct_change')
        title = f"TOP {n} BIGGEST PRICE INCREASES"
        sign = "+"
    else:
        top = df[df['pct_change'] < 0].nsmallest(n, 'pct_change')
        title = f"TOP {n} BIGGEST PRICE DECREASES"
        sign = ""

    if top.empty:
        print(f"No {'increases' if increases else 'decreases'} found.")
        return top

    print(f"\n{title}:")
    print("=" * 105)
    print(f"{'migrosId':<15} {'Product':<30} {'Quantity':<12} {'Old':>8} {'New':>8} {'Change':>9} {'Date':<12}")
    print("-" * 105)

    for _, row in top.iterrows():
        change_str = f"{sign}{row['pct_change']:.1f}%"
        qty_str = str(row['quantity'])[:10]
        print(f"{row['migrosId']:<15} {row['name'][:28]:<30} {qty_str:<12} "
              f"{row['old_price']:>7.2f} {row['new_price']:>7.2f} {change_str:>9} {str(row['date'])[:10]:<12}")

    return top


# =============================================================================
# API UNIT PRICE QUALITY ANALYSIS
# =============================================================================

def analyze_api_unit_price_quality(products: list) -> dict:
    """
    Analyze API unit price quality by comparing with self-calculated values.

    Args:
        products: List of MongoDB product documents

    Returns:
        Dictionary with statistics and mismatch examples
    """
    stats = {
        'total': 0,
        'has_api_unit_price': 0,
        'can_calculate': 0,
        'both_available': 0,
        'matches': 0,
        'mismatches': [],
        'mismatch_categories': {
            '1000x_error': 0,
            '100x_error': 0,
            '10x_error': 0,
            '2-10x_error': 0,
            'minor_diff': 0
        }
    }

    for p in products:
        stats['total'] += 1

        offer = p.get('offer', {})
        price_obj = offer.get('price', {})
        effective = price_obj.get('effectiveValue')
        quantity = offer.get('quantity', '')
        api_unit = price_obj.get('unitPrice', {})

        if not effective or effective <= 0:
            continue

        has_api = api_unit and api_unit.get('value') and api_unit.get('unit')
        calc_price, calc_unit = parse_quantity_to_unit_price(quantity, effective)
        can_calc = calc_price is not None

        if has_api:
            stats['has_api_unit_price'] += 1
        if can_calc:
            stats['can_calculate'] += 1

        if has_api and can_calc:
            stats['both_available'] += 1
            api_val = api_unit['value']

            # Calculate ratio (how far off is API from calculated)
            ratio = max(api_val, calc_price) / max(min(api_val, calc_price), 0.001)

            if ratio <= 1.1:  # Within 10% - consider a match
                stats['matches'] += 1
            else:
                # Categorize the error
                if ratio >= 500:
                    stats['mismatch_categories']['1000x_error'] += 1
                elif ratio >= 50:
                    stats['mismatch_categories']['100x_error'] += 1
                elif ratio >= 5:
                    stats['mismatch_categories']['10x_error'] += 1
                elif ratio >= 2:
                    stats['mismatch_categories']['2-10x_error'] += 1
                else:
                    stats['mismatch_categories']['minor_diff'] += 1

                stats['mismatches'].append({
                    'migrosId': p['migrosId'],
                    'name': p.get('name', 'Unknown'),
                    'quantity': quantity,
                    'effective': effective,
                    'api_unit_price': api_val,
                    'api_unit': api_unit.get('unit'),
                    'calc_unit_price': round(calc_price, 2),
                    'calc_unit': calc_unit,
                    'ratio': round(ratio, 1),
                    'error_type': categorize_error(ratio)
                })

    # Sort mismatches by ratio (worst first)
    stats['mismatches'] = sorted(stats['mismatches'], key=lambda x: -x['ratio'])

    return stats


def categorize_error(ratio: float) -> str:
    """Categorize the error based on ratio."""
    if ratio >= 500:
        return "~1000x (decimal error)"
    elif ratio >= 50:
        return "~100x (decimal error)"
    elif ratio >= 5:
        return "~10x (multipack error)"
    elif ratio >= 2:
        return "2-10x (calculation error)"
    else:
        return "minor (<2x)"


def print_api_quality_report(stats: dict, show_examples: int = 15):
    """Print a formatted API quality report."""
    print("\n" + "=" * 80)
    print("API UNIT PRICE QUALITY ANALYSIS")
    print("=" * 80)

    print(f"\nCoverage:")
    print(f"  Total products analyzed:    {stats['total']:,}")
    print(f"  Has API unit price:         {stats['has_api_unit_price']:,} ({stats['has_api_unit_price']/stats['total']*100:.1f}%)")
    print(f"  Can calculate from qty:     {stats['can_calculate']:,} ({stats['can_calculate']/stats['total']*100:.1f}%)")
    print(f"  Both available (comparable): {stats['both_available']:,}")

    if stats['both_available'] > 0:
        total_mismatches = len(stats['mismatches'])
        match_rate = stats['matches'] / stats['both_available'] * 100

        print(f"\nAccuracy (where both available):")
        print(f"  Matches (within 10%):       {stats['matches']:,} ({match_rate:.1f}%)")
        print(f"  Mismatches:                 {total_mismatches:,} ({100-match_rate:.1f}%)")

        print(f"\nMismatch breakdown:")
        for cat, count in stats['mismatch_categories'].items():
            if count > 0:
                print(f"  {cat.replace('_', ' '):20} {count:,}")

        if show_examples > 0 and stats['mismatches']:
            print(f"\nWorst {min(show_examples, len(stats['mismatches']))} API errors:")
            print("-" * 100)
            print(f"{'migrosId':<14} {'Product':<25} {'Qty':<12} {'API':<12} {'Calculated':<12} {'Error'}")
            print("-" * 100)

            for m in stats['mismatches'][:show_examples]:
                api_str = f"{m['api_unit_price']:.2f}/{m['api_unit']}"
                calc_str = f"{m['calc_unit_price']:.2f}/{m['calc_unit']}"
                print(f"{m['migrosId']:<14} {m['name'][:23]:<25} {m['quantity'][:10]:<12} "
                      f"{api_str:<12} {calc_str:<12} {m['error_type']}")

    return stats


# =============================================================================
# CALORIE EXTRACTION AND PRICE PER CALORIE
# =============================================================================

def extract_calories(product: dict) -> float | None:
    """
    Extract calories (kcal) per 100g/100ml from a product document.

    Args:
        product: MongoDB product document with productInformation.nutrientsInformation

    Returns:
        kcal per 100g/100ml, or None if not found
    """
    nutrients_info = product.get('productInformation', {}).get('nutrientsInformation', {})

    # Method 1: Direct energyKcal field (rare but check anyway)
    if nutrients_info.get('energyKcal'):
        try:
            return float(nutrients_info['energyKcal'])
        except:
            pass

    # Method 2: Search nutrientsTable
    nutrients_table = nutrients_info.get('nutrientsTable', {})

    # Handle dict format with 'rows' structure (common Migros format)
    if isinstance(nutrients_table, dict) and 'rows' in nutrients_table:
        for row in nutrients_table['rows']:
            if not isinstance(row, dict):
                continue
            label = str(row.get('label', '')).lower()
            values = row.get('values', [])

            # Look for Energy row
            if 'energy' in label or 'energie' in label:
                if values and len(values) > 0:
                    val_str = str(values[0])

                    # Parse formats like "0.9 kJ (0.2 kcal)" or "1680 kJ / 400 kcal"
                    # Try to extract kcal value first
                    kcal_match = re.search(r'(\d+(?:[.,]\d+)?)\s*kcal', val_str, re.IGNORECASE)
                    if kcal_match:
                        try:
                            return float(kcal_match.group(1).replace(',', '.'))
                        except:
                            pass

                    # Try kJ and convert (1 kcal = 4.184 kJ)
                    kj_match = re.search(r'(\d+(?:[.,]\d+)?)\s*kJ', val_str, re.IGNORECASE)
                    if kj_match:
                        try:
                            kj = float(kj_match.group(1).replace(',', '.'))
                            return kj / 4.184
                        except:
                            pass

    # Handle list format (older structure)
    elif isinstance(nutrients_table, list):
        for n in nutrients_table:
            if not isinstance(n, dict):
                continue
            name = str(n.get('name', '')).lower()
            value = n.get('value', '')

            if 'kcal' in name or ('energ' in name and 'kj' not in name):
                try:
                    val_str = str(value).replace('kcal', '').replace('Kcal', '').strip()
                    return float(val_str.replace(',', '.'))
                except:
                    pass

            if 'kj' in name:
                try:
                    val_str = str(value).replace('kJ', '').replace('kj', '').strip()
                    kj = float(val_str.replace(',', '.'))
                    return kj / 4.184
                except:
                    pass

    return None


def calculate_price_per_calorie(product: dict) -> dict | None:
    """
    Calculate price per 1000 kcal for a product.

    Math:
        - kcal_per_100g = from nutrition table
        - price_per_100g = effective_price / (quantity_in_grams / 100)
        - price_per_1000kcal = (price_per_100g / kcal_per_100g) * 1000

    Or equivalently:
        - total_calories = (quantity_in_grams / 100) * kcal_per_100g
        - price_per_1000kcal = (effective_price / total_calories) * 1000

    Args:
        product: MongoDB product document

    Returns:
        Dict with price_per_1000kcal, kcal_per_100g, etc. or None if can't calculate
    """
    # Get calories per 100g/100ml
    kcal_per_100 = extract_calories(product)
    if not kcal_per_100 or kcal_per_100 <= 0:
        return None

    # Get effective price
    offer = product.get('offer', {})
    price = offer.get('price', {}).get('effectiveValue')
    if not price or price <= 0:
        return None

    # Parse quantity to get total amount in g or ml
    quantity_str = offer.get('quantity', '')
    amount, unit_type = parse_quantity_amount(quantity_str)
    if not amount or amount <= 0:
        return None

    # Calculate price per 100g/100ml
    price_per_100 = (price / amount) * 100

    # Calculate price per 1000 kcal
    # price_per_100 is CHF per 100g, kcal_per_100 is kcal per 100g
    # So price per kcal = price_per_100 / kcal_per_100
    # Price per 1000 kcal = (price_per_100 / kcal_per_100) * 1000
    price_per_1000kcal = (price_per_100 / kcal_per_100) * 1000

    return {
        'price_per_1000kcal': price_per_1000kcal,
        'price_per_100': price_per_100,
        'kcal_per_100': kcal_per_100,
        'effective_price': price,
        'quantity': quantity_str,
        'amount': amount,
        'unit_type': unit_type
    }


def analyze_calorie_extraction(products: list) -> dict:
    """
    Analyze calorie extraction to understand failure cases.

    Args:
        products: List of MongoDB product documents with nutrition data

    Returns:
        Dict with statistics and failure examples
    """
    stats = {
        'total': len(products),
        'has_nutrients_table': 0,
        'calories_extracted': 0,
        'calories_zero': 0,
        'quantity_parseable': 0,
        'price_per_calorie_ok': 0,
        'failures': {
            'no_nutrients_table': [],
            'no_energy_row': [],
            'parse_failed': [],
            'quantity_unparseable': [],
            'zero_calories': []
        }
    }

    for p in products:
        nutrients_info = p.get('productInformation', {}).get('nutrientsInformation', {})
        nutrients_table = nutrients_info.get('nutrientsTable')

        if not nutrients_table:
            stats['failures']['no_nutrients_table'].append({
                'migrosId': p.get('migrosId'),
                'name': p.get('name', 'Unknown')[:40]
            })
            continue

        stats['has_nutrients_table'] += 1

        # Try to extract calories
        kcal = extract_calories(p)

        if kcal is None:
            # Debug: find out why
            if isinstance(nutrients_table, dict) and 'rows' in nutrients_table:
                energy_row = None
                for row in nutrients_table['rows']:
                    if isinstance(row, dict):
                        label = str(row.get('label', '')).lower()
                        if 'energy' in label or 'energie' in label:
                            energy_row = row
                            break

                if energy_row:
                    stats['failures']['parse_failed'].append({
                        'migrosId': p.get('migrosId'),
                        'name': p.get('name', 'Unknown')[:40],
                        'energy_values': energy_row.get('values', [])
                    })
                else:
                    stats['failures']['no_energy_row'].append({
                        'migrosId': p.get('migrosId'),
                        'name': p.get('name', 'Unknown')[:40],
                        'row_labels': [r.get('label') for r in nutrients_table.get('rows', []) if isinstance(r, dict)][:5]
                    })
            continue

        if kcal == 0:
            stats['calories_zero'] += 1
            stats['failures']['zero_calories'].append({
                'migrosId': p.get('migrosId'),
                'name': p.get('name', 'Unknown')[:40]
            })
            # Zero calories is valid (e.g., water, diet drinks) - still count as extracted
            stats['calories_extracted'] += 1
            continue

        stats['calories_extracted'] += 1

        # Check if quantity is parseable
        quantity_str = p.get('offer', {}).get('quantity', '')
        amount, unit = parse_quantity_amount(quantity_str)

        if amount:
            stats['quantity_parseable'] += 1
            stats['price_per_calorie_ok'] += 1
        else:
            stats['failures']['quantity_unparseable'].append({
                'migrosId': p.get('migrosId'),
                'name': p.get('name', 'Unknown')[:40],
                'quantity': quantity_str,
                'kcal': kcal
            })

    return stats


def print_calorie_extraction_report(stats: dict, show_examples: int = 5):
    """Print a formatted calorie extraction analysis report."""
    print("\n" + "=" * 80)
    print("CALORIE EXTRACTION ANALYSIS")
    print("=" * 80)

    print(f"\nOverview:")
    print(f"  Products with nutrition data:  {stats['total']:,}")
    print(f"  Has nutrientsTable:            {stats['has_nutrients_table']:,} ({stats['has_nutrients_table']/stats['total']*100:.1f}%)")
    print(f"  Calories extracted:            {stats['calories_extracted']:,} ({stats['calories_extracted']/stats['total']*100:.1f}%)")
    print(f"  - of which zero calories:      {stats['calories_zero']:,}")
    print(f"  Quantity parseable:            {stats['quantity_parseable']:,}")
    print(f"  Full price/calorie calculable: {stats['price_per_calorie_ok']:,} ({stats['price_per_calorie_ok']/stats['total']*100:.1f}%)")

    print(f"\nFailure breakdown:")
    for failure_type, examples in stats['failures'].items():
        if examples:
            print(f"  {failure_type.replace('_', ' ')}: {len(examples):,}")

    # Show examples of each failure type
    if show_examples > 0:
        for failure_type, examples in stats['failures'].items():
            if examples and len(examples) > 0:
                print(f"\n  Examples of '{failure_type}':")
                for ex in examples[:show_examples]:
                    if 'energy_values' in ex:
                        print(f"    {ex['migrosId']}: {ex['name']} - values: {ex['energy_values']}")
                    elif 'row_labels' in ex:
                        print(f"    {ex['migrosId']}: {ex['name']} - labels: {ex['row_labels']}")
                    elif 'quantity' in ex:
                        print(f"    {ex['migrosId']}: {ex['name']} - qty: '{ex['quantity']}' ({ex.get('kcal', 'N/A')} kcal)")
                    else:
                        print(f"    {ex['migrosId']}: {ex['name']}")


def find_price_per_calorie_changes(products: list, min_change_pct: float = 1.0,
                                    max_calorie_change_pct: float = 50.0) -> pd.DataFrame:
    """
    Find products where price per calorie changed over time.

    This can detect:
    1. Price increases (same calories, higher price)
    2. Quality-flation (same price, fewer calories -> higher price/kcal)
    3. Reformulation (calories changed significantly)

    Args:
        products: List of MongoDB product documents
        min_change_pct: Minimum percentage change to report
        max_calorie_change_pct: Maximum calorie change to include (filters data errors)
                                Changes >50% are likely data format changes, not real recipe changes

    Returns:
        DataFrame with price-per-calorie changes
    """
    # Build price-per-calorie data for each product observation
    data = []
    for p in products:
        calc = calculate_price_per_calorie(p)
        if calc is None:
            continue

        data.append({
            'migrosId': p['migrosId'],
            'name': p.get('name', 'Unknown'),
            'dateAdded': p.get('dateAdded'),
            **calc
        })

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    df['dateAdded'] = pd.to_datetime(df['dateAdded'])
    df = df.sort_values(['migrosId', 'dateAdded'])

    # Find changes
    changes = []
    for migros_id, group in df.groupby('migrosId'):
        if len(group) < 2:
            continue

        group = group.sort_values('dateAdded')

        for i in range(1, len(group)):
            old = group.iloc[i-1]
            new = group.iloc[i]

            old_ppc = old['price_per_1000kcal']
            new_ppc = new['price_per_1000kcal']

            if old_ppc <= 0:
                continue

            ppc_change_pct = ((new_ppc - old_ppc) / old_ppc) * 100

            # Also track calorie changes (for quality-flation detection)
            old_kcal = old['kcal_per_100']
            new_kcal = new['kcal_per_100']
            kcal_change_pct = ((new_kcal - old_kcal) / old_kcal) * 100 if old_kcal > 0 else 0

            # Price per 100g change
            old_price = old['price_per_100']
            new_price = new['price_per_100']
            price_change_pct = ((new_price - old_price) / old_price) * 100 if old_price > 0 else 0

            # Filter out extreme calorie changes (likely data errors, not real recipe changes)
            # E.g., stock cubes showing 254->4 kcal is a data format change, not reformulation
            if abs(kcal_change_pct) > max_calorie_change_pct:
                continue

            if abs(ppc_change_pct) >= min_change_pct:
                changes.append({
                    'migrosId': migros_id,
                    'name': new['name'],
                    'date': new['dateAdded'],
                    'old_price_per_1000kcal': old_ppc,
                    'new_price_per_1000kcal': new_ppc,
                    'ppc_change_pct': ppc_change_pct,
                    'old_kcal_per_100': old_kcal,
                    'new_kcal_per_100': new_kcal,
                    'kcal_change_pct': kcal_change_pct,
                    'old_price_per_100': old_price,
                    'new_price_per_100': new_price,
                    'price_change_pct': price_change_pct,
                    'old_quantity': old['quantity'],
                    'new_quantity': new['quantity']
                })

    return pd.DataFrame(changes)


def print_quality_flation(df: pd.DataFrame, n: int = 20):
    """
    Print quality-flation cases: where calories dropped significantly.

    Quality-flation = product got worse (fewer calories) while price stayed similar,
    so you're paying more per calorie.
    """
    if df.empty:
        print("No price-per-calorie data available.")
        return df

    # Filter for cases where calories dropped significantly (>5%)
    quality_flation = df[df['kcal_change_pct'] < -5].copy()

    if quality_flation.empty:
        print("No quality-flation cases found (calories dropped >5%).")
        return quality_flation

    # Sort by calorie drop (most shrunk first)
    quality_flation = quality_flation.nsmallest(n, 'kcal_change_pct')

    print(f"\nQUALITY-FLATION: Top {min(n, len(quality_flation))} products where calories dropped >5%")
    print("(Higher price per calorie = worse value for consumer)")
    print("=" * 130)
    print(f"{'migrosId':<14} {'Product':<28} {'Old kcal':>10} {'New kcal':>10} {'kcal Chg':>10} {'Price/kcal Chg':>14} {'Date':<12}")
    print("-" * 130)

    for _, row in quality_flation.iterrows():
        print(f"{row['migrosId']:<14} {row['name'][:26]:<28} "
              f"{row['old_kcal_per_100']:>9.1f} {row['new_kcal_per_100']:>9.1f} "
              f"{row['kcal_change_pct']:>+9.1f}% {row['ppc_change_pct']:>+13.1f}% "
              f"{str(row['date'])[:10]:<12}")

    return quality_flation


# =============================================================================
# LEGACY FUNCTIONS (kept for backward compatibility)
# =============================================================================

def normalize_unit_type(unit_type: str) -> str:
    """Normalize unit type to '100g' or '100ml'."""
    if not unit_type:
        return None
    if unit_type in ('100g', '100ml'):
        return unit_type
    elif 'g' in unit_type.lower():
        return '100g'
    elif 'l' in unit_type.lower() or 'ml' in unit_type.lower():
        return '100ml'
    elif 'piece' in unit_type.lower() or 'stk' in unit_type.lower():
        return None
    return None


def extract_unit_price(product: dict) -> tuple:
    """
    Extract unit price from a product document.
    LEGACY: Use build_price_history_df() for price tracking instead.
    """
    offer = product.get('offer', {})
    price_obj = offer.get('price', {})
    effective = price_obj.get('effectiveValue')
    unit_price_obj = price_obj.get('unitPrice', {})
    quantity = offer.get('quantity', '')

    if not effective or effective <= 0:
        return None, None, False

    if unit_price_obj and unit_price_obj.get('value') and unit_price_obj.get('unit'):
        unit_price = unit_price_obj['value']
        unit_type = unit_price_obj['unit']

        if unit_price / effective > 200:
            return None, None, False

        if quantity:
            calculated_price, _ = parse_quantity_to_unit_price(quantity, effective)
            if calculated_price is not None:
                ratio = max(unit_price, calculated_price) / max(min(unit_price, calculated_price), 0.001)
                if ratio > 10:
                    return calculated_price, normalize_unit_type(unit_type), True

        return unit_price, normalize_unit_type(unit_type), False

    if quantity:
        calculated_price, calculated_unit = parse_quantity_to_unit_price(quantity, effective)
        if calculated_price is not None:
            return calculated_price, calculated_unit, True

    return None, None, False


def build_price_dataframe(products: list) -> pd.DataFrame:
    """LEGACY: Use build_price_history_df() instead."""
    data = []
    stats = {'calculated': 0, 'skipped': 0}

    for p in products:
        unit_price, unit_type, was_calculated = extract_unit_price(p)

        if unit_price is None or unit_type is None:
            stats['skipped'] += 1
            continue

        if was_calculated:
            stats['calculated'] += 1

        data.append({
            'migrosId': p['migrosId'],
            'name': p.get('name', 'Unknown'),
            'unitPrice': unit_price,
            'unitType': unit_type,
            'effectiveValue': p.get('offer', {}).get('price', {}).get('effectiveValue'),
            'quantity': p.get('offer', {}).get('quantity', ''),
            'dateAdded': p.get('dateAdded')
        })

    df = pd.DataFrame(data)
    if not df.empty:
        df['dateAdded'] = pd.to_datetime(df['dateAdded'])
        df = df.sort_values(['migrosId', 'dateAdded'])

    return df, stats


def find_price_changes(df: pd.DataFrame, min_change_pct: float = 1.0) -> pd.DataFrame:
    """LEGACY: Use find_price_changes_v2() instead."""
    changes = []

    for migros_id, group in df.groupby('migrosId'):
        if len(group) <= 1:
            continue

        group = group.sort_values('dateAdded')

        for i in range(1, len(group)):
            old_row = group.iloc[i-1]
            new_row = group.iloc[i]

            if old_row['unitType'] != new_row['unitType']:
                continue

            old_price = old_row['unitPrice']
            new_price = new_row['unitPrice']

            if old_price > 0 and abs(new_price - old_price) / old_price > (min_change_pct / 100):
                abs_change = new_price - old_price
                pct_change = ((new_price - old_price) / old_price) * 100

                changes.append({
                    'migrosId': migros_id,
                    'name': new_row['name'],
                    'quantity': new_row['quantity'],
                    'old_price': old_price,
                    'new_price': new_price,
                    'abs_change': abs_change,
                    'pct_change': pct_change,
                    'date': new_row['dateAdded'],
                    'unitType': new_row['unitType']
                })

    return pd.DataFrame(changes)


def filter_outliers(df: pd.DataFrame,
                   min_price: float = 0.05,
                   max_price: float = 500,
                   max_pct_change: float = 100) -> pd.DataFrame:
    """LEGACY: Use filter_price_changes() instead."""
    return df[
        (df['old_price'] >= min_price) &
        (df['old_price'] <= max_price) &
        (df['pct_change'].abs() <= max_pct_change)
    ].copy()


def print_top_changes(df: pd.DataFrame, n: int = 20, increases: bool = True):
    """LEGACY: Use print_price_changes() instead."""
    if increases:
        top = df[df['abs_change'] > 0].nlargest(n, 'pct_change')
        title = f"TOP {n} BIGGEST PRICE INCREASES"
        sign = "+"
    else:
        top = df[df['abs_change'] < 0].nsmallest(n, 'pct_change')
        title = f"TOP {n} BIGGEST PRICE DECREASES"
        sign = ""

    print(f"\n{title} (per 100g/100ml):")
    print("=" * 115)
    print(f"{'migrosId':<15} {'Product':<32} {'Old':>8} {'New':>8} {'Unit':<6} {'Change':>9} {'Date':<12}")
    print("-" * 115)

    for _, row in top.iterrows():
        change_str = f"{sign}{row['pct_change']:.1f}%"
        print(f"{row['migrosId']:<15} {row['name'][:30]:<32} {row['old_price']:>7.2f} "
              f"{row['new_price']:>7.2f} {row['unitType']:<6} {change_str:>9} {str(row['date'])[:10]:<12}")

    return top
