"""
Shared settings, kept in one place so both the data-fetching scripts and the
screening scripts can use them without depending on each other.

(The screener reads only from the local database, so it should NOT have to
import the Angel One login code just to know which symbol it's looking at.)
"""

EXCHANGE = "NSE"
SYMBOL = "RELIANCE-EQ"
SYMBOL_TOKEN = "2885"   # Angel One's numeric id for RELIANCE-EQ on NSE
INTERVAL = "ONE_DAY"
