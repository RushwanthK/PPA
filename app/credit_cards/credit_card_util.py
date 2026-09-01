from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
#from .. import db
#from ..utils import money

def calculate_current_cycle_start(billing_cycle_start):
    """Calculate the start date of the current billing cycle"""
    today = datetime.now(timezone.utc)
    
    if today.day >= billing_cycle_start:
        # Current month's cycle
        try:
            return today.replace(day=billing_cycle_start)
        except ValueError:
            # Handle invalid day for current month (e.g., 31 in April)
            next_month = today.replace(day=1) + timedelta(days=32)
            last_day = (next_month.replace(day=1) - timedelta(days=1)).day
            adjusted_day = min(billing_cycle_start, last_day)
            return today.replace(day=adjusted_day)
    else:
        # Previous month's cycle
        if today.month == 1:
            prev_month = 12
            prev_year = today.year - 1
        else:
            prev_month = today.month - 1
            prev_year = today.year
            
        try:
            return datetime(prev_year, prev_month, billing_cycle_start)
        except ValueError:
            # Last day of previous month
            last_day = (datetime(prev_year, prev_month, 1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            return last_day

def get_billing_cycle_range(reference_date, billing_day):
    """
    Given a reference date and billing cycle start day, 
    return the current cycle's start and end date.
    """
    if reference_date.day >= billing_day:
        cycle_start = reference_date.replace(day=billing_day)
    else:
        # Move to previous month
        prev_month = reference_date.replace(day=1) - timedelta(days=1)
        cycle_start = prev_month.replace(day=billing_day)

    # Calculate end as one day before next cycle start
    try:
        next_cycle_start = cycle_start + relativedelta(months=1)
        cycle_end = next_cycle_start - timedelta(days=1)
    except ValueError:
        # Handle overflow (e.g., February 30)
        last_day = (cycle_start + relativedelta(months=1)).replace(day=1) - timedelta(days=1)
        cycle_end = last_day

    return cycle_start, cycle_end

"""
def is_in_current_billing_cycle(transaction_date, cycle_start_day):
    #Check if transaction falls in current billing cycle based on CURRENT DATE
    today = datetime.now(timezone.utc)
    
    # Calculate current cycle start date
    if today.day >= cycle_start_day:
        # Current cycle started earlier this month
        try:
            cycle_start = today.replace(day=cycle_start_day)
        except ValueError:
            # Handle invalid day for current month
            next_month = today.replace(day=1) + timedelta(days=32)
            last_day = (next_month.replace(day=1) - timedelta(days=1)).day
            cycle_start_day = min(cycle_start_day, last_day)
            cycle_start = today.replace(day=cycle_start_day)
    else:
        # Current cycle started previous month
        prev_month = today.month - 1 if today.month > 1 else 12
        prev_year = today.year if today.month > 1 else today.year - 1
        
        try:
            cycle_start = datetime(prev_year, prev_month, cycle_start_day)
        except ValueError:
            # Last day of previous month
            cycle_start = datetime(prev_year, prev_month, 1) + timedelta(days=32)
            cycle_start = cycle_start.replace(day=1) - timedelta(days=1)
    
    return transaction_date >= cycle_start

def process_billing_date_transition(card):
    #Call this when a card's billing date arrives
    # Move unbilled spends to billed_unpaid
    card.billed_unpaid = money(card.billed_unpaid + card.unbilled_spends)
    card.unbilled_spends = 0
    db.session.commit()
"""